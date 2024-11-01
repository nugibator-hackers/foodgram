from django.contrib.auth import get_user_model
from drf_extra_fields.fields import Base64ImageField
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.serializers import ModelSerializer

from backend.constants import MAXVALUE, MINVALUE, RECIPES_LIMIT_DEFAULT
from recipes.models import (Ingredient, Recipe, RecipeIngredient, Tag)
from users.models import Follow

User = get_user_model()


class TagSerializer(ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class IngredientSerializer(ModelSerializer):
    class Meta:
        model = Ingredient
        fields = '__all__'


class PasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Текущий пароль неверен.")
        return value

    def validate(self, data):
        if not data.get('current_password') or not data.get('new_password'):
            raise serializers.ValidationError(
                'Требуется указать текущий и новый пароли.'
            )
        return data

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = ['avatar']

    def validate(self, data):
        request = self.context.get('request')
        if request.method in ['PUT', 'PATCH']:
            if not data or 'avatar' not in data:
                raise serializers.ValidationError(
                    {'avatar': 'Поле "avatar" обязательно для обновления.'}
                )
        return data

    def update(self, instance, validated_data):
        instance.avatar = validated_data.get('avatar', instance.avatar)
        instance.save()
        return instance


class UsersSerializer(UserSerializer):
    is_subscribed = SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )

    def get_is_subscribed(self, obj):
        user = self.context['request'].user
        if user.is_anonymous or user == obj:
            return False
        return obj.subscribing.filter(user=user).exists()


class UsersCreateSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password'
        )

    def validate_username(self, value):
        if value.lower() == 'me':
            raise serializers.ValidationError(
                'Невозможно создать аккаунт с username "me!"'
            )
        return value

    def get_response(self):
        response_data = {
            key: value
            for key, value in self.data.items()
            if key not in ['is_subscribed', 'avatar']}
        return response_data


class ReadIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit')
    amount = serializers.IntegerField()

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class ReadRecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit')
    amount = serializers.ReadOnlyField()

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeReadSerializer(ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UsersSerializer(read_only=True)
    image = Base64ImageField()
    ingredients = ReadRecipeIngredientSerializer(
        source='ingredient_list', many=True
    )
    is_favorited = SerializerMethodField(read_only=True)
    is_in_shopping_cart = SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )

    def is_user_anonymous(self):
        return self.context['request'].user.is_anonymous

    def get_is_favorited(self, obj):
        if self.is_user_anonymous():
            return False
        user = self.context['request'].user
        return user.favorites.filter(recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        if self.is_user_anonymous():
            return False
        user = self.context['request'].user
        return user.shopping_cart.filter(recipe=obj).exists()


class RecipeIngredientWriteSerializer(ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    amount = serializers.IntegerField(
        min_value=MINVALUE,
        max_value=MAXVALUE,
        error_messages={
            'min_value':
                f'Количество ингредиентов должно быть больше {MINVALUE}',
            'max_value':
                f'Количество ингредиентов должно быть меньше {MAXVALUE}',
        }
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


class RecipeWriteSerializer(ModelSerializer):
    tags = PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True
    )
    author = UsersSerializer(read_only=True)
    image = Base64ImageField()
    ingredients = RecipeIngredientWriteSerializer(
        source='ingredient_list', many=True,
    )
    cooking_time = serializers.IntegerField(
        min_value=MINVALUE,
        max_value=MAXVALUE,
        error_messages={
            'min_value': f'Время приготовления не менее {MINVALUE} минут!',
            'max_value': f'Время приготовления не более {MAXVALUE} минут!',
        }
    )

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'name',
            'image',
            'text',
            'cooking_time',
        )

    def validate(self, data):
        if 'ingredient_list' not in data:
            raise ValidationError(
                {"ingredients": "В запросе не передано поле."})

        if 'tags' not in data:
            raise ValidationError(
                {"tags": "В запросе не передано поле."})

        return data

    def validate_image(self, value):
        if not value:
            raise ValidationError('Поле "image" не может быть пустым!')

        return value

    # def validate_ingredients(self, value):
    #     ingredients = value
    #     if not ingredients:
    #         raise ValidationError(
    #             {'ingredients': 'Нужен хотя бы один ингредиент!'}
    #         )

    #     ingredients_list = set()

    #     for item in ingredients:
    #         if 'id' not in item['ingredient']:
    #             raise ValidationError(
    #               {'ingredients': 'Указан некорректный формат ингредиента!'}
    #             )

    #         try:
    #             ingredient = Ingredient.objects.get(
    #                 id=item['ingredient']['id'])
    #         except Ingredient.DoesNotExist:
    #             raise ValidationError(
    #                 {'ingredients': 'Ингредиент не существует!'}
    #             )

    #         amount = item.get('amount')
    #         if amount is None or amount < 1:
    #             raise ValidationError({
    #                 'amount': (
    #                     'Количество ингредиентов должно быть больше 1'
    #                 )
    #             })

    #         if ingredient in ingredients_list:
    #             raise ValidationError(
    #                 {'ingredients': 'Ингредиенты не могут повторяться!'}
    #             )

    #         ingredients_list.append(ingredient)

    #     return value
    def validate_ingredients(self, value):
        ingredients = value
        if (
            ingredients is None
            or not isinstance(ingredients, list)
            or len(ingredients) == 0
        ):
            raise ValidationError(
                {'ingredients': 'Нужен хотя бы один ингредиент!'}
            )

        ingredients_set = set()
        ingredient_ids = set()

        for item in ingredients:
            ingredient_id = item['ingredient']['id']
            if ingredient_id in ingredient_ids:
                raise ValidationError(
                   {'ingredients': 'Ингредиенты не могут повторяться!'}
                    )
            ingredient_ids.add(ingredient_id)
            ingredients_set.add(ingredient_id)

        return value

    # def validate_tags(self, value):
    #     tags = value
    #     if not tags:
    #         raise ValidationError(
    #             {'tags': 'Нужно выбрать хотя бы один тег!'}
    #         )
    #     tags_list = []
    #     for tag in tags:
    #         if tag in tags_list:
    #             raise ValidationError(
    #                 {'tags': 'Теги должны быть уникальными!'}
    #             )
    #         tags_list.append(tag)
    #     return value
    def validate_tags(self, value):
        tags = value
        if not tags:
            raise ValidationError(
                {'tags': 'Нужно выбрать хотя бы один тег!'}
            )

        tags_set = set()  # Множество для хранения уникальных тегов

        for tag in tags:
            if tag in tags_set:
                raise ValidationError(
                    {'tags': 'Теги должны быть уникальными!'}
                )
            tags_set.add(tag)  # Добавляем тег в множество

        return value

    def create_ingredients(self, ingredients, recipe):
        RecipeIngredient.objects.filter(recipe=recipe).delete()
        instances = [
            RecipeIngredient(
                ingredient_id=ingredient['ingredient']['id'],
                recipe=recipe,
                amount=ingredient['amount']
            )
            for ingredient in ingredients
        ]
        RecipeIngredient.objects.bulk_create(instances)

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredient_list')
        tags_data = validated_data.pop('tags', [])
        user = self.context['request'].user
        recipe = Recipe.objects.create(author=user, **validated_data)
        recipe.tags.set(tags_data)
        self.create_ingredients(ingredients_data, recipe)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredient_list')
        tags_data = validated_data.pop('tags')

        instance = super().update(instance, validated_data)
        instance.tags.set(tags_data)
        instance.ingredient_list.clear()
        self.create_ingredients(ingredients_data, instance)
        return instance

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return RecipeReadSerializer(instance, context=context).data


class SubscriptionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='author.id')
    username = serializers.CharField(source='author.username')
    first_name = serializers.CharField(source='author.first_name')
    last_name = serializers.CharField(source='author.last_name')
    email = serializers.EmailField(source='author.email')
    avatar = serializers.ImageField(source='author.avatar', allow_null=True)
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = Follow
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email',
            'avatar', 'is_subscribed', 'recipes', 'recipes_count'
        )

    def get_is_subscribed(self, instance):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return instance.author.subscribing.filter(user=request.user
                                                      ).exists()
        return False

    def get_recipes(self, instance):
        request = self.context.get('request')
        recipes_limit = int(request.query_params.get('recipes_limit',
                                                     RECIPES_LIMIT_DEFAULT))
        recipes = instance.author.recipes.all()[:recipes_limit]
        return RecipeShortSerializer(recipes, many=True).data

    def get_recipes_count(self, instance):
        return instance.author.recipes.count()

    def validate(self, attrs):
        user = attrs.get('user')
        author = attrs.get('author')

        if user == author:
            raise ValidationError(
                {'detail': 'Вы не можете подписаться на себя.'})

        return attrs


class SimpleUserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name',
                  'last_name', 'email', 'avatar', 'is_subscribed')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.subscribing.filter(user=request.user).exists()
        return False


class RecipeShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
