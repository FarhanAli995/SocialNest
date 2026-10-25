# SocialNest

SocialNest is a full-featured social networking web application built with **Django**. Users can share text, photos, and videos, follow other people, and interact through likes and comments. It also includes rich user profiles, a searchable Explore page, personalized feeds, notifications, and real-time direct messaging.

---

## Screenshots

| Feed / Home (`homepage.jpeg`) | Explore (`explore_site.jpeg`) |
| --- | --- |
| ![SocialNest home feed displaying post creation, multimedia posts with engagement options, trending topics, and active contacts](static/images/homepage.jpeg) | ![SocialNest explore page showing user search, recommended people cards, and a grid of community posts](static/images/explore_site.jpeg) |
| The home feed allows users to share text, photos, and videos, view posts from followed accounts, engage with likes and comments, and track trending hashtags and active contacts. | The explore page helps users discover new people and trending content across the platform with search functionality and preview cards. |

| User Profile (`profile.jpeg`) | Notifications (`notiffications.jpeg`) |
| --- | --- |
| ![SocialNest user profile page showing avatar, join date, follower statistics, follow button, and content tabs](static/images/profile.jpeg) | ![SocialNest notifications list displaying follow alerts with timestamps and read status controls](static/images/notiffications.jpeg) |
| The profile page displays user avatars, bio, join date, follower and following metrics, follow/unfollow actions, and tabbed views for posts, media, and likes. | The notifications view alerts users to recent interactions such as new followers, likes, and comments, with options to mark individual or all notifications as read. |

| Login (`Login_site.jpeg`) | Registration (`registration site.jpeg`) |
| --- | --- |
| ![SocialNest login portal featuring credentials form, password visibility toggle, remember me option, and quick switch to register](static/images/Login_site.jpeg) | ![SocialNest registration form with fields for full name, email, password confirmation, terms acceptance, and account creation](static/images/registration%20site.jpeg) |
| Secure authentication interface allowing existing users to sign in with email/username and password, complete with password visibility controls and remember me options. | Onboarding page allowing new users to create an account by providing their details, setting up credentials, and agreeing to platform terms. |

| Inbox (`inbox.png`) | Chat (`chat.png`) |
| --- | --- |
| ![SocialNest inbox with a list of direct conversations, profile initials, latest message previews, and an empty-conversation preview](static/images/inbox.png) | ![SocialNest direct-message conversation displayed in light and dark themes, with incoming and outgoing messages, timestamps, online status, and a message composer](static/images/chat.png) |
| The inbox brings direct conversations together, showing each user's initial, username, latest message preview, and an empty state when no messages have been sent. | The chat view shows a one-to-one conversation in both light and dark themes, with distinct incoming and outgoing messages, timestamps, the participant's online status, and the message input. |

---

## Features

- **Authentication** - Register, log in, and log out (logout via secure POST).
- **Profiles** - Avatar, cover image, bio, location, and website. Editable profile page.
- **Posts** - Create posts with text (up to 280 chars), images, and video uploads.
- **Feed** - Personalized feed showing your posts and the people you follow.
- **Explore** - Browse and search all posts and people.
- **Likes & Comments** - Like/unlike posts and add comments; counts are tracked.
- **Follow system** - Follow/unfollow users and see follower/following counts.
- **Block users** - Block/unblock users, remove mutual follows, and restrict profile, feed, and chat access.
- **Notifications** - Get notified on likes, comments, and new followers; mark one or all as read.
- **Direct messaging** - Start one-to-one conversations, view recent conversations and message previews in the inbox, and see unread message counts.
- **Real-time chat** - Exchange messages instantly over WebSockets, with typing indicators, read receipts, saved message history, and automatic reconnection after a dropped connection.
- **Search** - Search posts by text/author and people by username/name.

## Real-Time Chat

Direct messages use Django Channels and a WebSocket connection at `/ws/chat/<room_id>/`. The authenticated chat consumer checks room membership and block status, saves messages to the database, and broadcasts them to connected participants. The chat room displays recent messages and updates live; typing status and read events are also sent over the WebSocket. The inbox shows each conversation's latest message and unread count.

For local development, the channel layer uses in-memory storage. This works with a single server process; configure a shared channel layer such as Redis for multi-process or production deployments.

---

## Tech Stack

- **Backend:** Django (Python), Django Channels, Daphne
- **Database:** SQLite (development)
- **Frontend:** Django templates, custom CSS and vanilla JavaScript, Font Awesome icons, Google Fonts (Inter)
- **Real-time messaging:** Django Channels and Daphne, with an in-memory channel layer for development
- **Media:** Local file storage for avatars, covers, and post media

---

## Project Structure

    socialNest/
    |-- accounts/          # Auth, profiles, follow system
    |-- posts/             # Posts, comments, likes, feed, explore
    |-- notifications/     # Notification model, list, mark-read
    |-- chat/              # Direct messages, WebSocket consumer and chat views
    |-- socialNest/        # Project settings and root URLs
    |-- static/            # CSS, JS, images (screenshots)
    |-- templates/         # HTML templates
    |-- media/             # User uploads (gitignored)
    |-- manage.py
    `-- db.sqlite3         # Dev database (gitignored)

---


## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

1. Clone the repository:

       git clone https://github.com/FarhanAli995/codeAlpha_SocialNest.git
       cd codeAlpha_SocialNest

2. Create and activate a virtual environment:

       python -m venv venv
       source venv/bin/activate      # macOS / Linux
       venv/Scripts/activate         # Windows

3. Install dependencies:

       python -m pip install django pillow "channels==4.3.2" "daphne==4.2.3"

4. Apply migrations:

       python manage.py migrate

5. Create a superuser (optional):

       python manage.py createsuperuser

6. Run the development server:

       python manage.py runserver

   Daphne is enabled in `INSTALLED_APPS` and provides the ASGI-capable development `runserver` command needed for WebSockets.

7. Open your browser at http://127.0.0.1:8000/

The development channel layer uses in-memory storage, which is appropriate for a single local server process. For a multi-process or production deployment, configure a shared channel layer such as Redis.

---

## Main Routes

| URL | Name | Description |
| --- | --- | --- |
| / | posts:feed | Personalized feed |
| /explore/ | posts:explore | Explore posts and people |
| /create/ | posts:post_create | Create a new post |
| /<pk>/ | posts:post_detail | Post detail with comments |
| /<pk>/like/ | posts:like_toggle | Like / unlike (POST) |
| /<pk>/comment/ | posts:add_comment | Add a comment (POST) |
| /accounts/register/ | accounts:register | Sign up |
| /accounts/login/ | accounts:login | Log in |
| /accounts/logout/ | accounts:logout | Log out (POST) |
| /accounts/profile/ | accounts:own_profile | Your profile |
| /accounts/profile/<username>/ | accounts:profile_detail | Another user's profile |
| /chat/ | chat:inbox | Direct-message inbox |
| /chat/start_chat/<user_id>/ | chat:start | Start or open a direct chat |
| /chat/room/<room_id>/ | chat:room | Chat room |
| /chat/room/<room_id>/history/?before=<message_id> | chat:history | Load older messages (JSON) |
| /notifications/ | notifications:list | Notifications |

---

## Notes

- The db.sqlite3 database and the media/ folder are gitignored and not committed. Run migrations after cloning to create the database.
- Logout requires a POST request (Django 5+ security behavior); the logout button submits a form with a CSRF token.

---

## License

This project was built as part of the **CodeAlpha** internship program.
