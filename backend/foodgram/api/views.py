from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from recipes.models import Ingredient, Tag, Recipe, Favorite, ShoppingCart, CountIngredientInRecipe
from users.models import Subscribe
from .serializers import IngredientSerializers, TagSerializers, RecipeSerializer, UserSerializer, SubscribeSerializers, RecipeCreateUpdateSerializer, FavoriteSerializer
from rest_framework.response import Response
from rest_framework import status
from users.models import User
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import Sum
from django.http import HttpResponse
from api.pagination import PagePagination
from api.permission import AuthorOrReadOnly
from djoser.views import UserViewSet as DjoserUserViewSet

class IngredientViewSet(ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializers

class TagViewSet(ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializers

class RecipeViewSet(ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    pagination_class = PagePagination
    permission_classes = [AuthorOrReadOnly]

    def perform_create(self, serializer):
        return serializer.save(author=self.request.user)
    
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
    @action(
        detail=False,
        methods=['GET']
    )
    def download_shopping_cart(self, request):
        ingredients = (
            CountIngredientInRecipe.objects.filter(
                recipecartuser=request.user)
            .order_by('ingredientname')
            .values('ingredientname', 'ingredientmeasurement_unit')
            .annotate(ingredient_value=Sum('amount')))

        if not ingredients:
            return Response(status=status.HTTP_204_NO_CONTENT)

        shopping_list = (
            f'Foodgram пользователь {request.user} - список покупок\n\n'
        )

        for ingredient in ingredients:
            item = (
                f'• {ingredient["ingredientname"]} - '
                f'{ingredient["ingredient_value"]} '
                f'{ingredient["ingredient__measurement_unit"]}'
            )
            shopping_list += item + '\n'

        filename = 'foodgram_shopping_list.txt'
        response = HttpResponse(shopping_list, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={filename}'

        return response

    def get_serializer_class(self):
        if self.action in ['retrieve', 'get_link']:
            return RecipeSerializer
        return RecipeCreateUpdateSerializer

class UserViewSet(DjoserUserViewSet):
    queryset = User.objects.all()
    # serializer_class = UserSerializer

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def subscribes(self, request, id):
        user = request.user
        author = get_object_or_404(User, id=id)
        if request.method == 'POST':
            serializer = SubscribeSerializers(
                author,
                data=request.data,
                context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            sub = Subscribe.objects.cerate(user=user, author=author)
            sub.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        if request.method == 'DELETE':
            sub = get_object_or_404(
                Subscribe,
                user=user,
                author=author
            )
            sub.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
    @action(
        methods=['GET'],
        detail=True,
        permission_classes=[IsAuthenticated]
    )
    def is_subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(follow__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = SubscribeSerializers(
            pages,
            many=True,
            context={'request': request}
        )
        return self.get_paginated_response(serializer.data)