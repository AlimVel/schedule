from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from .models import InviteLink, User

def index(request):
    return render(request, 'index.html')

def auth(request):
    # Если юзер уже вошел, проверяем его роль и кидаем на нужный дашборд
    if request.user.is_authenticated:
        if request.user.is_admin:
            return redirect('dashboard')
        elif request.user.is_teacher:
            return redirect('teacher_dashboard')

    context = {}
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            login(request, user)
            # При успешном входе тоже проверяем роль
            if user.is_admin:
                return redirect('dashboard')
            elif user.is_teacher:
                return redirect('teacher_dashboard')
            else:
                return redirect('index') # Если роль не определена
        else:
            context['error'] = 'Неверный логин или пароль'

    return render(request, 'auth.html', context)

# Декоратор закрывает доступ: если юзер не авторизован, его перекинет на 'auth'
@login_required(login_url='auth')
def schedule(request):
    return render(request, 'schedule.html')

# Функция для выхода из аккаунта
def logout_view(request):
    logout(request)
    return redirect('index')

@login_required(login_url='auth')
def dashboard(request):
    # Здесь в будущем можно будет передавать реальные данные из базы
    return render(request, 'dashboard.html')

# Генерация ссылки (Доступно только авторизованным админам)
@login_required(login_url='auth')
def generate_invite(request):
    if not request.user.is_admin or not request.user.university:
        return HttpResponse("У вас нет прав для создания ссылки.", status=403)
    
    invite = InviteLink.objects.create(university=request.user.university)
    
    invite_url = request.build_absolute_uri(reverse('teacher_register', kwargs={'token': invite.token}))
    
    context = {
        'invite_url': invite_url,
        'university': request.user.university
    }
    return render(request, 'invite_success.html', context)

def teacher_register(request, token):
    # Проверяем, существует ли такая ссылка
    invite = get_object_or_404(InviteLink, token=token, is_active=True)
    university = invite.university
    
    context = {'university': university}

    if request.method == 'POST':
        # Собираем данные из красивой формы
        u = request.POST.get('username')
        p = request.POST.get('password')
        email = request.POST.get('email')
        last_name = request.POST.get('last_name')
        first_name = request.POST.get('first_name')
        middle_name = request.POST.get('middle_name')
        academic_title = request.POST.get('academic_title')

        # Проверка на занятость логина
        if User.objects.filter(username=u).exists():
            context['error'] = 'Этот логин уже занят. Попробуйте другой.'
            return render(request, 'teacher_register.html', context)

        # Создаем пользователя
        user = User.objects.create_user(
            username=u, 
            password=p, 
            email=email,
            first_name=first_name, 
            last_name=last_name,
            university=university, 
            is_teacher=True
        )
        # Добавляем кастомные поля
        user.middle_name = middle_name
        user.academic_title = academic_title
        user.save()
        
        # Перенаправляем на страницу входа
        return redirect('auth')

    # Если GET-запрос — просто показываем шаблон
    return render(request, 'teacher_register.html', context)

@login_required(login_url='auth')
def teacher_dashboard(request):
    # Дополнительная защита: пускаем сюда только преподавателей
    if not request.user.is_teacher:
        return redirect('dashboard')
    
    return render(request, 'teacher_dashboard.html')