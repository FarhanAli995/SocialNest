from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import blocked_user_ids, users_blocked
from posts.models import Follow

from .forms import StoryForm
from .models import Story, StoryView


def _visible_stories(user):
    """Active stories the viewer is allowed to see, grouped by author."""
    stories = Story.active().select_related('author', 'author__profile')
    if user.is_authenticated:
        following_ids = Follow.objects.filter(
            follower=user,
        ).values_list('following_id', flat=True)
        blocked = blocked_user_ids(user)
        stories = stories.filter(
            Q(author=user) | Q(author_id__in=following_ids)
        ).exclude(author_id__in=blocked)
    else:
        return []

    groups = {}
    for story in stories.order_by('created_at'):
        groups.setdefault(story.author_id, {
            'author': story.author,
            'stories': [],
        })['stories'].append(story)
    return list(groups.values())


@login_required
def story_bar(request):
    """Returns JSON for the horizontal story ring bar."""
    groups = _visible_stories(request.user)
    viewed_ids = set(
        StoryView.objects.filter(
            viewer=request.user,
            story__in=Story.active(),
        ).values_list('story_id', flat=True)
    )

    payload = []
    for group in groups:
        author = group['author']
        story_ids = [s.pk for s in group['stories']]
        has_unseen = any(sid not in viewed_ids for sid in story_ids)
        payload.append({
            'author_id': author.pk,
            'username': author.username,
            'avatar': author.profile.avatar.url if author.profile.avatar else '',
            'initial': author.username[:1].upper(),
            'count': len(story_ids),
            'has_unseen': has_unseen,
            'is_self': author.pk == request.user.pk,
        })
    return JsonResponse({'groups': payload})


@login_required
def story_create(request):
    if request.method == 'POST':
        form = StoryForm(request.POST, request.FILES)
        if form.is_valid():
            story = form.save(commit=False)
            story.author = request.user
            story.save()
            messages.success(request, 'Story added. It will disappear in 24 hours.')
            return redirect('posts:feed')
    else:
        form = StoryForm()
    return render(request, 'stories/story_form.html', {'form': form})


@login_required
def story_viewer(request, user_id):
    """Full-screen viewer for one author's active stories."""
    if int(user_id) != request.user.pk and users_blocked(
        request.user, get_object_or_404(
            Story.active().model._meta.get_field('author').related_model,
            pk=user_id,
        ),
    ):
        raise Http404

    stories = list(
        Story.active()
        .filter(author_id=user_id)
        .select_related('author', 'author__profile')
        .order_by('created_at')
    )
    if not stories:
        raise Http404

    author = stories[0].author
    return render(request, 'stories/story_viewer.html', {
        'stories': stories,
        'author': author,
        'is_own': author.pk == request.user.pk,
    })


@login_required
@require_POST
def mark_viewed(request, story_id):
    story = get_object_or_404(Story, pk=story_id)
    if story.author_id == request.user.pk:
        return JsonResponse({'ok': True})
    if users_blocked(request.user, story.author):
        raise Http404
    StoryView.objects.get_or_create(story=story, viewer=request.user)
    return JsonResponse({'ok': True})


@login_required
@require_POST
def story_delete(request, story_id):
    story = get_object_or_404(Story, pk=story_id, author=request.user)
    story.delete()
    messages.success(request, 'Story deleted.')
    return redirect('posts:feed')


@login_required
def story_viewers(request, story_id):
    story = get_object_or_404(Story, pk=story_id, author=request.user)
    viewers = story.views.select_related('viewer', 'viewer__profile')
    return render(request, 'stories/story_viewers.html', {
        'story': story,
        'viewers': viewers,
    })
