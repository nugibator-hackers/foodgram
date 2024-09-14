from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    first_name = models.CharField(
        'Имя',
        max_length=100
    )
    last_name = models.CharField(
        'Фамилия',
        max_length=100
    )
    username = models.CharField(
        'Ник',
        max_length=100,
        unique=True
    )
    email = models.EmailField(
        'Email',
        max_length=100,
        unique=True
    )

    class Meta:
        ordering = ('username',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username
    
class Subscribe(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriber',
        verbose_name='Подписчик'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='author',
        verbose_name='Автор'
    )
    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'author',),
                name='unique_user_author'
            )
        ]
    def __str__(self):
        return (f'{self.user.username} подписался '
                f'на {self.author.username}')
