from rest_framework import serializers
from recipes.models import Ingredient, Tag, Recipe, CountIngredientInRecipe, Favorite, ShoppingCart
from users.models import User, Follow
from django.contrib.auth import get_user_model
from drf_extra_fields.fields import Base64ImageField
User = get_user_model()

class IngredientSerializers(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = '__all__'


class TagSerializers(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'
    
class CountIngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = CountIngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')

class IngredientForRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = CountIngredientInRecipe
        fields = (
            'id',
            'name',
            'measurement_unit',
            'amount',
        )

class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = '__all__'
        


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name',
                  'username', 'email', 'password', 'is_subscribed')

    def get_is_subscribed(self, obj):
        current_user = self.context.get('request').user
        if current_user.is_anonymous:
            return False
        return Follow.objects.filter(user=current_user, author=obj).exists()

class RecipeAndShoppingCartSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')

class ShopingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCart
        fields = '__all__'

    def validate(self, data):
        if not self.context.get('request').method == 'POST':
            return data
        if Favorite.objects.filter(
            user=data['user'],
            recipe=data['recipe']
        ).exists():
            raise serializers.ValidationError(
                'Рецепт уже добавлен'
            )
        return data

    def to_representation(self, instance):
        return RecipeAndShoppingCartSerializer(
            instance.recipe, context={
                'request': self.context.get('request')
            }
        ).data

class RecipeSerializer(serializers.ModelSerializer):
    image = Base64ImageField()
    tags = TagSerializers(many=True)
    ingredients = CountIngredientInRecipeSerializer(
        many=True,
        source='countingredientinrecipe'
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    author = UserSerializer(read_only=True)

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        if user.is_anonymous or user is None:
            return False
        return Favorite.objects.filter(
            user=user,
            recipe=obj
        ).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        if user.is_anonymous or user is None:
            return False
        return ShoppingCart.objects.filter(
            user=user,
            recipe=obj
        ).exists()
    
    
class CreateUserSerializers(UserSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name',
                  'username', 'email', 'password',)
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'username': {'required': True},
            'email': {'required': True},
            'password': {'required': True},
        }
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=User.objects.all(),
                fields=('email', 'username'),
                message="Логин и email должны быть уникальными"
            )
        ]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class FollowSerializers(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes', 'recipes_count')
        read_only_fields = ('id', 'first_name', 'last_name',
                            'username', 'email', 'is_subscribed',
                            'recipes', 'recipes_count')
    def get_recipes_count(self, obj):
        return obj.recipes.count
    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes_limit = request.GET.get('recipes_limit')
        recipes = obj.recipes.all()[:int(recipes_limit)] if recipes_limit else obj.recipes.all()
        serializer = RecipeSerializer(recipes, many=True, read_only=True)
        return serializer.data
    
class CreateFollowSerializer(serializers.ModelSerializer):

    class Meta:
        model = Follow
        fields = ('user', 'author')
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Follow.objects.all(),
                fields=('author', 'user'),
                message='Невозможно подписаться, так как вы уже подписаны'
            )
        ]

    def validate(self, data):
        if data['user'] == data['author']:
            raise serializers.ValidationError(
                'Нельзя подписаться на себя'
            )
        return data

    def to_representation(self, instance):
        return FollowSerializers(
            instance.author, context={
                'request': self.context.get('request')
            }
        ).data
    

class RecipeIngredientCreateSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all()
    )
    amount = serializers.IntegerField()

    class Meta:
        model = CountIngredientInRecipe
        fields = ('id', 'amount')

    def validate_amount(self, value):
        if value < 1:
            raise serializers.ValidationError(
                f'Количество продукта ({value}) '
                f'меньше минимально допустимого (1).'
            )
        return value

class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    image = Base64ImageField()
    ingredients = RecipeIngredientCreateSerializer(many=True, source='countingredientinrecipe')
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )

    class Meta:
        model = Recipe
        fields = (
            'name',
            'ingredients',
            'tags',
            'text',
            'image',
            'cooking_time',
            'id',
        )
        read_only_fields = ('author',)

    def to_representation(self, instance):
        return RecipeSerializer(instance, context=self.context).data

    @staticmethod
    def validate_items(items, model, field_name):
        if not items:
            raise serializers.ValidationError(
                {field_name: f'Поле {field_name} не может быть пустым.'}
            )
        existing_items = model.objects.filter(
            id__in=items
        ).values_list('id', flat=True)
        missing_items = set(items) - set(existing_items)
        if missing_items:
            raise serializers.ValidationError(
                {field_name: f'Элемент(ы) с id {missing_items} не существует!'}
            )
        non_unique_ids = set(
            item for item in items if items.count(item) > 1
        )
        if non_unique_ids:
            raise serializers.ValidationError(
                {field_name: f'Элементы с id {non_unique_ids} не уникальны!'}
            )

    def validate(self, data):
        tags = self.initial_data.get('tags')
        ingredients = self.initial_data.get('ingredients')
        if not ingredients:
            raise serializers.ValidationError(
                'Поле "ingredients" не может быть пустым.'
            )
        ingredients_ids = [item['id'] for item in ingredients]
        self.validate_items(
            ingredients_ids,
            model=Ingredient,
            field_name='ingredients',
        )
        self.validate_items(
            tags,
            model=Tag,
            field_name='tags',
        )
        return data

    def set_ingredients(self, recipe, ingredients):
        for ingredient in ingredients:
            CountIngredientInRecipe.objects.create(
                recipe=recipe,
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            )

    def create(self, validated_data):
        image_data = validated_data.pop('image')
        tag = validated_data.pop('tags')
        ingredients = validated_data.pop('countingredientinrecipe')
        recipe = Recipe.objects.create(image=image_data, **validated_data)
        recipe.tags.set(tag)
        self.set_ingredients(ingredients=ingredients,
                               recipe=recipe)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('countingredientinrecipe')
        tags_data = validated_data.pop('tags')
        instance.save()
        instance.ingredients.clear()
        self.set_ingredients(instance, ingredients_data)
        instance.tags.set(tags_data)
        return super().update(instance, validated_data)