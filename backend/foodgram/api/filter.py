from django_filters.rest_framework import FilterSet, filters

from recipes.models import Ingredient, Tag, Recipe

class IngredientFilter(FilterSet):
    name = filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ('name',)

class RecipeFilter(FilterSet):
    tag = filters.ModelChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all()
    )
    favorite = filters.BooleanFilter(method='filter_favorite')
    shopping_cart = filters.BooleanFilter(method='filter_shopping_cart')

    class Meta:
        model = Recipe
        fields = ('tags', 'author',)

    def filter_favorite(self, queryset, name, value):
        if value:
            return queryset.filter(favoriteuser=self.request.user)
        return queryset

    def filter_shopping_cart(self, queryset, name, value):
        if value:
            return queryset.filter(shoppingcart__user=self.request.user)