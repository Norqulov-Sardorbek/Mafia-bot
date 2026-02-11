from django.contrib import admin
from django.utils import timezone

from .models import (
    User, UserRole, Game, PrizeHistory, MostActiveUser, BotMessages,
    PremiumGroup, CasesOpened, GroupTrials, PriceStones, MoneySendHistory,
    GameSettings, BotCredentials, LoginAttempts
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id", "telegram_id", "username", "first_name", "role", "lang",
        "coin", "stones", "is_vip","is_hero",
    )
    list_filter = ("role", "lang", "is_vip", "is_hero",)
    search_fields = ("telegram_id", "username", "first_name")
    ordering = ("-id",)
    readonly_fields = ("telegram_id",)

    fieldsets = (
        ("Asosiy", {"fields": ("telegram_id", "username", "first_name", "lang", "role")}),
        ("Balans", {"fields": ("coin", "stones", "premium_stones") if hasattr(User, "premium_stones") else ("coin", "stones")}),
        ("Status", {"fields": ("is_vip", "active_role")}),
        ("Qo‘shimcha", {"fields": ("protection", "docs","hang_protect","is_protected","is_hang_protected","is_doc","is_geroy_protected")}),
    )

    def get_fieldsets(self, request, obj=None):
        base = [
            ("Asosiy", {"fields": ("telegram_id", "username", "first_name", "lang", "role")}),
            ("Balans", {"fields": ("coin", "stones")}),
            ("Status", {"fields": ("is_vip", "is_hero", "active_role")}),
             ("Qo‘shimcha", {"fields": ("protection", "docs","hang_protect","is_protected","is_hang_protected","is_doc","is_geroy_protected")}),
        ]
        return base


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "role_key", "quantity", "created_datetime")
    list_filter = ("role_key",)
    search_fields = ("user__username", "user__telegram_id", "role_key")
    ordering = ("-id",)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "chat_id", "lang", "is_started", "is_ended", "is_active_game", "created_datetime")
    list_filter = ("lang", "is_started", "is_ended", "is_active_game")
    search_fields = ("chat_id",)
    ordering = ("-id",)


@admin.register(PrizeHistory)
class PrizeHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "period", "start_date", "end_date")
    list_filter = ("period",)
    search_fields = ("group",)
    ordering = ("-id",)


@admin.register(MostActiveUser)
class MostActiveUserAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "group", "games_played", "games_win", "created_datetime")
    list_filter = ("group",)
    search_fields = ("user__username", "user__telegram_id", "group")
    ordering = ("-games_played", "-games_win")


@admin.register(BotMessages)
class BotMessagesAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "message_id", "is_main", "is_deleted", "created_datetime")
    list_filter = ("is_main", "is_deleted")
    search_fields = ("message_id", "game__id", "game__chat_id")
    ordering = ("-id",)


@admin.register(PremiumGroup)
class PremiumGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "group_id", "name", "stones_for", "ends_date", "created_datetime")
    list_filter = ("ends_date",)
    search_fields = ("group_id", "name")
    ordering = ("-ends_date",)


@admin.register(CasesOpened)
class CasesOpenedAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "money_case", "stone_case", "created_datetime")
    list_filter = ("money_case", "stone_case")
    search_fields = ("user__username", "user__telegram_id")
    ordering = ("-id",)


@admin.register(GroupTrials)
class GroupTrialsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "group_id", "group_name", "group_username",
        "coins", "stones", "premium_stones",
        "start_date", "end_date", "prem_ends_date"
    )
    list_filter = ("start_date", "end_date", "prem_ends_date")
    search_fields = ("group_id", "group_name", "group_username")
    ordering = ("-id",)
    readonly_fields = ("start_date",)


@admin.register(PriceStones)
class PriceStonesAdmin(admin.ModelAdmin):
    list_display = ("id", "created_datetime")
    ordering = ("-id",)


@admin.register(MoneySendHistory)
class MoneySendHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "receiver", "amount", "created_datetime")
    list_filter = ("created_datetime",)
    search_fields = ("sender__username", "receiver__username", "sender__telegram_id", "receiver__telegram_id")
    ordering = ("-id",)


@admin.register(GameSettings)
class GameSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "group_id", "begin_instance",
        "begin_instance_time", "number_of_players", "begin_after_end", "created_datetime"
    )
    list_filter = ("begin_instance", "begin_after_end")
    search_fields = ("group_id", "user__username", "user__telegram_id")
    ordering = ("-id",)


@admin.register(BotCredentials)
class BotCredentialsAdmin(admin.ModelAdmin):
    list_display = ("id",  "login", "created_datetime")
    search_fields = ("login",)
    ordering = ("-id",)


@admin.register(LoginAttempts)
class LoginAttemptsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "admin", "attempts", "is_banned_display",
        "ban_until", "permanent_ban", "last_attempt", "created_datetime"
    )
    list_filter = ("permanent_ban", "ban_until", "last_attempt")
    search_fields = ("admin__username", "admin__telegram_id")
    ordering = ("-id",)

    actions = ("unban_users", "ban_forever", "ban_1_day")

    @admin.display(description="Ban status")
    def is_banned_display(self, obj):
        if obj.permanent_ban:
            return "🚫 PERMANENT"
        if obj.ban_until and obj.ban_until > timezone.now():
            return "⏳ TEMP BAN"
        return "✅ OK"

    @admin.action(description="✅ Unban qilish")
    def unban_users(self, request, queryset):
        queryset.update(permanent_ban=False, ban_until=None, attempts=0)

    @admin.action(description="🚫 Umrbod ban qilish")
    def ban_forever(self, request, queryset):
        queryset.update(permanent_ban=True, ban_until=None)

    @admin.action(description="⏳ 1 kunga ban qilish")
    def ban_1_day(self, request, queryset):
        until = timezone.now() + timezone.timedelta(days=1)
        for obj in queryset:
            obj.ban_until = until
            obj.permanent_ban = False
            obj.save(update_fields=["ban_until", "permanent_ban"])
