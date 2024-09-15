from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from recipes.models import Ingredient, Tag, Recipe, Favorite, ShoppingCart, CountIngredientInRecipe
from users.models import Subscribe  
from .serializers import IngredientSerializers, TagSerializers, RecipeSerializer, UserSerializer, SubscribeSerializers, RecipeCreateUpdateSerializer, FavoriteSerializer, ShopingCartSerializer
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import Sum
from django.http import HttpResponse
from api.pagination import PagePagination
from api.permission import AuthorOrReadOnly
from djoser.views import UserViewSet as DjoserUserViewSet
from django.contrib.auth import get_user_model
from api.filter import IngredientFilter, RecipeFilter
from django_filters.rest_framework import DjangoFilterBackend

User = get_user_model()

class IngredientViewSet(ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializers
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
class TagViewSet(ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializers

class RecipeViewSet(ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    pagination_class = PagePagination
    permission_classes = [AuthorOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
    
    def add_recipe(self, user, model, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        if model.objects.filter(user=user, recipe=recipe):
            return Response(
                {'errors': 'Этот рецепт уже был добавлен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = FavoriteSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete_recipe(self, model, user, recipe_id):
        obj = model.objects.filter(user=user, recipe_id=recipe_id)
        if obj.exists():
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {'errors': 'Невозможно удалить рецепт'},
            status=status.HTTP_400_BAD_REQUEST
        )
    @action(
            methods=['POST', 'DELETE'],
            detail=True,
            permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk):
        if request.method == 'POST':
            return self.add_recipe(Favorite, request.user, pk)
        if request.method == 'DELETE':
            return self.delete_recipe(Favorite, request.user, pk)
    @action(
            methods=['POST', 'DELETE'],
            detail=True,
            permission_classes=[IsAuthenticated]
    )
    def use_shopping_cart(self, request, pk):
        if request.method == 'POST':
            return self.add_recipe(ShoppingCart, request.user, pk)
        if request.method == 'DELETE':
            return self.delete_recipe(ShoppingCart, request.user, pk)
    
    @staticmethod
    def shopping_cart_txt(ingredients):
        shopping_cart = 'Список покупок:\n'
        shopping_cart += ''.join([
            f'{ingredient["ingredient__name"]} '
            f'{ingredient["amount"]}'
            f'{ingredient["ingredient__measurement_unit"]}\n'
            for ingredient in ingredients
        ])
        return shopping_cart

    @action(
        detail=False,
        methods=['GET']
    )
    def download_shopping_cart(self, request):
        ingredients = CountIngredientInRecipe.objects.filter(
            recipe__shoppingcart__user=request.user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(amount=Sum('amount')).order_by('ingredient__name')
        shopping_cart = self.shopping_cart_txt(ingredients)
        response = HttpResponse(shopping_cart, content_type='text/plan')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_cart.txt')
        return response

    @action(
        methods=['POST'],
        detail=True,
        permission_classes=[IsAuthenticated],
    )
    def shopping_cart(self, request, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        context = {'request': request}
        data = {
            'user': request.user.id,
            'recipe': recipe.id
        }
        serializer = ShopingCartSerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED)

    def get_serializer_class(self):
        if self.action in ['retrieve', 'get_link']:
            return RecipeSerializer
        return RecipeCreateUpdateSerializer

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

class UserViewSet(DjoserUserViewSet):
    queryset = User.objects.all()
    pagination_class = PagePagination

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, id):
        author = get_object_or_404(User, id=id)
        data = {
            'author': author.id,
            'user': request.user.id
        }
        context = {'request': request}
        serializer = RecipeCreateUpdateSerializer(
            data=data,
            context=context
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def delete_subscribe(self, request, id):
        user = request.user
        author = get_object_or_404(User, id=id)
        sub = get_object_or_404(
            Subscribe,
            user=user,
            author=author
        )
        sub.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=['GET'],
        detail=False,
        permission_classes=[IsAuthenticated],
    )
    def subscriptions(self, request):
        queryset = User.objects.filter(follow__user=request.user)
        pages = self.paginate_queryset(queryset)
        serializer = SubscribeSerializers(
            pages,
            many=True,
            context={'request': request}
        )
        return self.get_paginated_response(serializer.data)