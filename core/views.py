from django.conf import settings
from django.contrib.auth import get_user_model, login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Count
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.translation import ugettext
from django.views import View

from .models import Profile, Thread, UnreadThread, Message
from .forms import AvatarForm

User = get_user_model()


class GetUserMixin(object):
    def get_user(self, request, username: str):
        # Anonymous user can't see another profile and can't edit.
        if not request.user.is_authenticated:
            return
        # Regular user and see another profile but can't edit.
        if not request.user.is_superuser and request.method == 'POST' and \
                username and username != request.user.username:
            raise PermissionDenied

        if username:
            return get_object_or_404(User, username=username)

        return request.user


@login_required
def user_list(request):
    """User list."""
    users = User.objects.exclude(id=request.user.id)\
        .values_list('username', flat=True).order_by('username')

    return render(request, 'user_list.html', {'users': users})


class ProfileView(View, GetUserMixin):
    """User profile."""
    def get(self, request, username):
        """View user profile."""
        user = GetUserMixin().get_user(request, username)
        if not user:
            return redirect_to_login(request.path)

        form = AvatarForm(data=request.POST)
        is_editing_allowed = user == request.user or request.user.is_superuser
        threads = Thread.objects.filter(users=user)\
            .order_by('-last_message').values_list('id', 'name')

        return render(request, 'profile.html', {
            'profile_user': user,
            'is_editing_allowed': is_editing_allowed,
            'form': form,
            'threads': threads,
        })

    def post(self, request, username):
        """Update user."""
        user = GetUserMixin().get_user(request, username)
        if not user:
            return redirect_to_login(request.path)

        avatar = request.FILES.get('avatar', '')
        if avatar:
            profile = get_object_or_404(Profile, user=user)
            form = AvatarForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            allowed_fields = ['first_name', 'last_name', 'email']
            field = request.POST.get('name', '')
            value = request.POST.get('value', '')
            if field and field in allowed_fields:
                setattr(user, field, value)
                try:
                    user.clean_fields()
                    user.save()
                    return JsonResponse({'success': True})
                except ValidationError as e:
                    return JsonResponse(
                        ', '.join(e.message_dict[field]),
                        safe=False,
                        status=422
                        )

        return JsonResponse(
            ugettext("You can't change this field"),
            safe=False,
            status=403
        )


@login_required
def thread_view(request, username=None, thread_id=None):
    """Thread page."""
    interlocutor = None
    if username:
        interlocutor = get_object_or_404(User, username=username)
        thread = Thread.objects\
            .annotate(count=Count('users'))\
            .filter(users=request.user)\
            .filter(users=interlocutor)\
            .filter(count=2)\
            .first()
        if not thread:
            thread = Thread(name=', '.join([request.user.username, username]))
            thread.save()
            thread.users.add(request.user, interlocutor)
    elif thread_id:
        thread = get_object_or_404(Thread, pk=thread_id)
    else:
        # username or thread_id should be passed.
        raise Http404

    # The user visited this tread - delete user's unread thread.
    UnreadThread.objects.filter(thread=thread, user=request.user).delete()

    # Prepare usernames and user avatars.
    users = {}
    for user in thread.users.all():
        profile, _ = Profile.objects.get_or_create(user=user)
        users[user.pk] = {
            'username': user.username,
            'avatar': profile.avatar.url,
        }

    # Get last 50 messages.
    messages = Message.objects.select_related('user').filter(thread=thread)\
                      .order_by('date')[:50]
    for message in messages:
        if message.user.pk not in users:
            try:
                avatar = message.user.profile.avatar.url
            except Profile.DoesNotExist:
                # If there no user profile - create it.
                profile, _ = Profile.objects.get_or_create(user=message.user)
                avatar = profile.avatar.url

            users[message.user.pk] = {
                'username': message.user.username,
                'avatar': avatar,
            }
    # Now we have all needed info - update messages.
    for message in messages:
        message.avatar = users[message.user.pk]['avatar']

    return render(request, 'thread.html', {
        'thread': thread,
        'messages': messages,
        'users': users,
        'interlocutor': interlocutor,
    })


@login_required
def call_view(request, username):
    """Call page."""
    interlocutor = get_object_or_404(User, username=username)

    return render(request, 'call.html', {
        'interlocutor': interlocutor,
    })


def log_in(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    form = AuthenticationForm()
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(reverse('core:user_list'))

    return render(request, 'login.html', {'form': form})


@login_required
def log_out(request):
    logout(request)
    return redirect(reverse(settings.LOGIN_URL))


def sign_up(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    form = UserCreationForm()
    if request.method == 'POST':
        form = UserCreationForm(data=request.POST)
        if form.is_valid():
            form.save()
            user = authenticate(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password1']
            )
            login(request, user)

            return redirect(reverse('core:user_list'))

    return render(request, 'signup.html', {'form': form})
