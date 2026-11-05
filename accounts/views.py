from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from notifications.models import Notification
from posts.models import Follow

from .forms import ProfileForm, SignUpForm
from .models import Profile, UserBlock, users_blocked


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    next_page = 'accounts:login'


def register(request):
    if request.user.is_authenticated:
        return redirect('posts:feed')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'Welcome to SocialNest!')
            return redirect('posts:feed')
    else:
        form = SignUpForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def own_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    posts = request.user.posts.all()
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'profile_user': request.user,
        'posts': posts,
        'is_own_profile': True,
    })


@login_required
def profile_detail(request, username):
    profile_user = get_object_or_404(User, username=username)
    if profile_user != request.user and users_blocked(request.user, profile_user):
        return redirect('posts:feed')

    profile, _ = Profile.objects.get_or_create(user=profile_user)
    is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists()
    follows_you = Follow.objects.filter(
        follower=profile_user,
        following=request.user,
    ).exists()
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'profile_user': profile_user,
        'posts': profile_user.posts.all(),
        'is_own_profile': profile_user == request.user,
        'is_following': is_following,
        'follows_you': follows_you,
        'followers_count': profile_user.followers.count(),
        'following_count': profile_user.following.count(),
    })


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)

            # Remove the current custom avatar if the user asked to clear it
            # and did not upload a replacement in the same request.
            if request.POST.get('avatar-clear') and not request.FILES.get('avatar'):
                if profile.avatar and profile.avatar.name and profile.avatar.name != 'avatars/default.png':
                    profile.avatar.delete(save=False)
                profile.avatar = 'avatars/default.png'

            profile.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:own_profile')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'accounts/edit_profile.html', {'form': form})


@login_required
@require_POST
def follow_toggle(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        messages.error(request, 'You cannot follow yourself.')
        return HttpResponseRedirect(reverse('accounts:profile_detail', args=[username]))
    if users_blocked(request.user, target):
        messages.error(request, 'You cannot follow a blocked user.')
        return redirect('posts:feed')

    follow, created = Follow.objects.get_or_create(follower=request.user, following=target)
    if not created:
        follow.delete()
        messages.info(request, f'Unfollowed {target.username}.')
    else:
        Notification.objects.create(
            recipient=target,
            sender=request.user,
            notif_type='follow',
        )
        messages.success(request, f'Now following {target.username}.')
    return HttpResponseRedirect(reverse('accounts:profile_detail', args=[username]))


@login_required
@require_POST
def block_toggle(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        messages.error(request, 'You cannot block yourself.')
        return redirect('accounts:own_profile')

    block = UserBlock.objects.filter(blocker=request.user, blocked=target).first()
    if block:
        block.delete()
        messages.success(request, f'Unblocked {target.username}.')
        return redirect('accounts:blocked_users')

    with transaction.atomic():
        UserBlock.objects.get_or_create(blocker=request.user, blocked=target)
        Follow.objects.filter(
            follower=request.user,
            following=target,
        ).delete()
        Follow.objects.filter(
            follower=target,
            following=request.user,
        ).delete()

    messages.success(request, f'Blocked {target.username}.')
    return redirect('accounts:own_profile')


@login_required
def blocked_users(request):
    blocks = UserBlock.objects.filter(
        blocker=request.user,
    ).select_related('blocked').order_by('blocked__username')
    return render(request, 'accounts/blocked_users.html', {'blocks': blocks})


@login_required
def friends_view(request):
    following_ids = request.user.following.values_list('following_id', flat=True)
    followers = request.user.followers.select_related('follower__profile').all()
    following = request.user.following.select_related('following__profile').all()
    suggestions = User.objects.exclude(id=request.user.id).exclude(id__in=following_ids)[:10]
    return render(request, 'accounts/friends.html', {
        'followers': followers,
        'following': following,
        'suggestions': suggestions,
    })


@login_required
def settings_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        if full_name:
            parts = full_name.split(' ', 1)
            request.user.first_name = parts[0]
            request.user.last_name = parts[1] if len(parts) > 1 else ''
        if email:
            request.user.email = email
        request.user.save()

        # Handle avatar if uploaded
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
            profile.save()

        messages.success(request, 'Settings saved successfully.')
        return redirect('accounts:settings')
    return render(request, 'accounts/settings.html', {'profile': profile})
