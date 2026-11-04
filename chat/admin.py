from django.contrib import admin

from .models import Call, ChatRoom, Message


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_group', 'created_at', 'updated_at')
    list_filter = ('is_group', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('participants',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'sender', 'message_type', 'timestamp', 'is_read')
    list_filter = ('is_read', 'message_type', 'timestamp')
    search_fields = ('content',)


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ('id', 'caller', 'receiver', 'status', 'created_at', 'duration')
    list_filter = ('status', 'call_type', 'created_at')
    search_fields = ('caller__username', 'receiver__username')
