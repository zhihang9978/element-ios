#!/usr/bin/env python3
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("ELEMENT_IOS_DIR", "element-ios"))
BUILD_REPO_ROOT = Path(__file__).resolve().parents[1]

HOMESERVER = "https://matrix.xuyoxxx.com"
SERVER_NAME = "matrix.xuyoxxx.com"
WEB_URL = "https://matrix.xuyoxxx.com"
APP_NAME = "绽友"
BASE_BUNDLE_ID = "com.xuyoxxx.zhanyou"
APP_GROUP_ID = ""
APP_SCHEME = "zhanyou"
LANGUAGE = "zh-Hans"
ICON_SOURCE = BUILD_REPO_ROOT / "branding" / "zhan-you-icon-1024.png"
ONBOARDING_ASSETS_DIR = BUILD_REPO_ROOT / "branding" / "onboarding"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def replace_regex(text: str, pattern: str, replacement: str, label: str, flags: int = 0) -> str:
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Could not patch {label}")
    return new_text


def replace_literal(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"Could not patch {label}")


def upsert_strings_key(text: str, key: str, value: str) -> str:
    line = f'"{key}" = "{value}";'
    pattern = rf'^{re.escape(chr(34) + key + chr(34))}\s*=\s*".*?";$'
    new_text, count = re.subn(pattern, line, text, flags=re.MULTILINE)
    if count:
        return new_text
    return text.rstrip() + "\n" + line + "\n"


def parse_strings(text: str) -> dict[str, str]:
    return dict(re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*=\s*"((?:\\.|[^"\\])*)";', text))


def apply_strings_overrides(text: str, overrides: dict[str, str], base_keys: set[str]) -> str:
    existing_keys = set(parse_strings(text))
    for key, value in overrides.items():
        if key in base_keys or key in existing_keys:
            text = upsert_strings_key(text, key, value)
    return text


def apply_brand_wording(text: str) -> str:
    return text.replace("Element", APP_NAME).replace("Matrix", APP_NAME)


def patch_build_settings() -> None:
    path = ROOT / "Config" / "BuildSettings.swift"
    text = read(path)

    text = replace_regex(
        text,
        r'static let applicationWebAppUrlString = "[^"]+"',
        f'static let applicationWebAppUrlString = "{WEB_URL}"',
        "applicationWebAppUrlString",
    )

    text = replace_regex(
        text,
        r'MDMSettings\.serverConfigDefaultHomeserverUrlString \?\? "[^"]+"',
        f'MDMSettings.serverConfigDefaultHomeserverUrlString ?? "{HOMESERVER}"',
        "default homeserver",
    )

    text = replace_regex(
        text,
        r'static let serverConfigDefaultIdentityServerUrlString = "[^"]+"',
        'static let serverConfigDefaultIdentityServerUrlString = ""',
        "identity server",
    )

    text = replace_regex(
        text,
        r'static var clientPermalinkBaseUrl: String\? \{\n\s*MDMSettings\.clientPermalinkBaseUrl\n\s*\}',
        f'static var clientPermalinkBaseUrl: String? {{\n        MDMSettings.clientPermalinkBaseUrl ?? "{WEB_URL}"\n    }}',
        "client permalink base URL",
        flags=re.MULTILINE,
    )

    if f'"{WEB_URL.replace("https://", "")}": ["/"]' not in text:
        text = text.replace(
            'static let permalinkSupportedHosts: [String: [String]] = [\n',
            f'static let permalinkSupportedHosts: [String: [String]] = [\n        "{WEB_URL.replace("https://", "")}": ["/"],\n',
            1,
        )

    text = replace_regex(
        text,
        r'static let stunServerFallbackUrlString: String\? = "[^"]+"',
        'static let stunServerFallbackUrlString: String? = "stun:matrix.xuyoxxx.com:3478"',
        "STUN fallback",
    )

    text = replace_regex(
        text,
        r'static let publicRoomsDirectoryServers = \[.*?\n\s*\]',
        f'static let publicRoomsDirectoryServers = [\n        "{SERVER_NAME}"\n    ]',
        "public room directory servers",
        flags=re.DOTALL,
    )

    text = replace_regex(
        text,
        r'static let authScreenShowCustomServerOptions = true',
        'static let authScreenShowCustomServerOptions = false',
        "custom server option",
    )

    text = replace_regex(
        text,
        r'static let replacementApp: ReplacementApp\? = \.init\(\)',
        'static let replacementApp: ReplacementApp? = nil',
        "replacement app banner",
    )

    # Keep Matrix/Element voice-video buttons enabled. The actual TURN server is provided by Synapse.
    text = replace_regex(
        text,
        r'static let roomScreenAllowVoIPForDirectRoom: Bool = (true|false)',
        'static let roomScreenAllowVoIPForDirectRoom: Bool = true',
        "direct room VoIP",
    )
    text = replace_regex(
        text,
        r'static let roomScreenAllowVoIPForNonDirectRoom: Bool = (true|false)',
        'static let roomScreenAllowVoIPForNonDirectRoom: Bool = true',
        "group room VoIP",
    )

    text = replace_regex(
        text,
        r'static let roomScreenTimelineDefaultStyleIdentifier: RoomTimelineStyleIdentifier = \.(plain|bubble)',
        'static let roomScreenTimelineDefaultStyleIdentifier: RoomTimelineStyleIdentifier = .bubble',
        "default room timeline style",
    )

    for setting in [
        "applicationCopyrightUrlString",
        "applicationPrivacyPolicyUrlString",
        "applicationAcceptableUsePolicyUrlString",
    ]:
        text = replace_regex(
            text,
            rf'static let {setting} = "[^"]*"',
            f'static let {setting} = ""',
            setting,
        )

    write(path, text)


def patch_app_identifiers() -> None:
    path = ROOT / "Config" / "AppIdentifiers.xcconfig"
    text = read(path)
    replacements = {
        "BUNDLE_DISPLAY_NAME": APP_NAME,
        "BASE_BUNDLE_IDENTIFIER": BASE_BUNDLE_ID,
        "APPLICATION_GROUP_IDENTIFIER": APP_GROUP_ID,
        "APPLICATION_SCHEME": APP_SCHEME,
        "DEVELOPMENT_TEAM": "",
        "RIOT_PROVISIONING_PROFILE_SPECIFIER": "",
        "RIOT_PROVISIONING_PROFILE": "",
        "NSE_PROVISIONING_PROFILE_SPECIFIER": "",
        "NSE_PROVISIONING_PROFILE": "",
        "SHARE_EXTENSION_PROVISIONING_PROFILE_SPECIFIER": "",
        "SHARE_EXTENSION_PROVISIONING_PROFILE": "",
        "SIRI_INTENTS_PROVISIONING_PROFILE_SPECIFIER": "",
        "SIRI_INTENTS_PROVISIONING_PROFILE": "",
        "BROADCAST_UPLOAD_EXTENSION_PROVISIONING_PROFILE_SPECIFIER": "",
        "BROADCAST_UPLOAD_EXTENSION_PROVISIONING_PROFILE": "",
    }
    for key, value in replacements.items():
        text = replace_regex(text, rf'^{re.escape(key)}\s*=.*$', f'{key} = {value}', key, flags=re.MULTILINE)
    write(path, text)


def patch_project_keychain_group() -> None:
    path = ROOT / "Config" / "Project.xcconfig"
    text = read(path)
    text = replace_regex(
        text,
        r'^KEYCHAIN_ACCESS_GROUP\s*=.*$',
        'KEYCHAIN_ACCESS_GROUP =',
        "project keychain access group",
        flags=re.MULTILINE,
    )
    write(path, text)


def patch_language() -> None:
    project_config = ROOT / "Config" / "Project.xcconfig"
    if project_config.exists():
        text = read(project_config)
        if "DEVELOPMENT_LANGUAGE" not in text:
            text = text.rstrip() + f"\n\n// Default localization for customized builds\nDEVELOPMENT_LANGUAGE = {LANGUAGE}\n"
            write(project_config, text)

    app_delegate = ROOT / "Riot" / "Modules" / "Application" / "AppDelegate.swift"
    text = read(app_delegate)
    if 'forKey: "AppleLanguages"' not in text:
        marker = "    func application(_ application: UIApplication, willFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {\n"
        insert = (
            marker
            + f"        UserDefaults.standard.set([\"{LANGUAGE}\"], forKey: \"AppleLanguages\")\n"
            + "        if !UserDefaults.standard.bool(forKey: \"zhanyouDefaultSettingsApplied\") {\n"
            + "            UserDefaults.standard.set(true, forKey: \"roomScreenEnableMessageBubbles\")\n"
            + "            RiotSettings.defaults.set(true, forKey: \"roomScreenEnableMessageBubbles\")\n"
            + "            UserDefaults.standard.set(true, forKey: \"zhanyouDefaultSettingsApplied\")\n"
            + "        }\n"
            + "        UserDefaults.standard.synchronize()\n"
        )
        if marker not in text:
            raise RuntimeError("Could not locate AppDelegate willFinishLaunchingWithOptions")
        text = text.replace(marker, insert, 1)
        write(app_delegate, text)


def patch_settings_about_buttons() -> None:
    path = ROOT / "Riot" / "Modules" / "Settings" / "SettingsViewController.m"
    text = read(path)
    text = replace_regex(
        text,
        r'\n    Section \*sectionAbout = \[Section sectionWithTag:SECTION_TAG_ABOUT\];\n.*?\n    \[tmpSections addObject:sectionAbout\];\n',
        "\n    // Zhanyou build: hide visible About legal and notice buttons from Settings.\n",
        "settings about visible buttons",
        flags=re.DOTALL,
    )
    write(path, text)


def patch_localized_strings() -> None:
    en_path = ROOT / "Riot" / "Assets" / "en.lproj" / "Vector.strings"
    zh_path = ROOT / "Riot" / "Assets" / "zh_Hans.lproj" / "Vector.strings"

    en_text = read(en_path)
    zh_text = read(zh_path)
    en_items = parse_strings(en_text)
    base_keys = set(en_items)

    overrides = {
        "view": "查看",
        "next": "下一步",
        "back": "返回",
        "continue": "继续",
        "create": "创建",
        "start": "开始",
        "leave": "离开",
        "remove": "移除",
        "invite": "邀请",
        "retry": "重试",
        "on": "开",
        "off": "关",
        "enable": "启用",
        "cancel": "取消",
        "save": "保存",
        "join": "加入",
        "decline": "拒绝",
        "accept": "接受",
        "preview": "预览",
        "camera": "相机",
        "voice": "语音",
        "video": "视频",
        "later": "稍后",
        "rename": "重命名",
        "close": "关闭",
        "skip": "跳过",
        "joining": "正在加入",
        "joined": "已加入",
        "switch": "切换",
        "more": "更多",
        "less": "更少",
        "open": "打开",
        "done": "完成",
        "private": "私密",
        "public": "公开",
        "stop": "停止",
        "new_word": "新建",
        "existing": "已有",
        "add": "添加",
        "ok": "确定",
        "error": "错误",
        "suggest": "建议",
        "edit": "编辑",
        "confirm": "确认",
        "delete": "删除",
        "copy_button_name": "复制",
        "resend": "重新发送",
        "redact": "移除",
        "share": "分享",
        "send": "发送",
        "loading": "正在加载",
        "sending": "正在发送",
        "saving": "正在保存",
        "home_empty_view_information": "绽友是一款安全的一体化聊天应用。点击下方「+」按钮添加联系人和房间。",
        "all_chats_empty_view_information": "绽友是一款安全的一体化聊天应用。创建聊天或加入现有房间即可开始。",
        "all_chats_empty_space_information": "空间可以把房间和联系人分组。添加已有房间或创建新房间即可开始。",
        "all_chats_empty_list_placeholder_title": "您已处理完所有消息。",
        "all_chats_empty_unreads_placeholder_message": "有未读消息时会显示在这里。",
        "all_chats_nothing_found_placeholder_title": "未找到结果。",
        "all_chats_nothing_found_placeholder_message": "请调整搜索条件后重试。",
        "all_chats_section_title": "聊天",
        "all_chats_user_menu_accessibility_label": "用户菜单",
        "all_chats_edit_layout": "布局偏好",
        "all_chats_edit_layout_recents": "最近聊天",
        "all_chats_edit_layout_unreads": "未读",
        "all_chats_edit_layout_add_section_title": "添加首页分区",
        "all_chats_edit_layout_add_section_message": "将分区固定到首页，便于快速访问",
        "all_chats_edit_layout_add_filters_title": "筛选消息",
        "all_chats_edit_layout_add_filters_message": "按您选择的类别自动筛选消息",
        "all_chats_edit_layout_pin_spaces_title": "固定您的空间",
        "all_chats_edit_layout_sorting_options_title": "消息排序方式",
        "all_chats_edit_layout_show_recents": "显示最近聊天",
        "all_chats_edit_layout_show_filters": "显示筛选器",
        "all_chats_edit_layout_activity_order": "按活跃度排序",
        "all_chats_edit_layout_alphabetical_order": "按字母顺序排序",
        "all_chats_all_filter": "全部",
        "all_chats_edit_menu_leave_space": "离开 %@",
        "all_chats_edit_menu_space_settings": "空间设置",
        "home_context_menu_make_dm": "移到私聊",
        "home_context_menu_make_room": "移到房间",
        "home_context_menu_notifications": "通知",
        "home_context_menu_mute": "静音",
        "home_context_menu_unmute": "取消静音",
        "home_context_menu_favourite": "收藏",
        "home_context_menu_unfavourite": "取消收藏",
        "home_context_menu_low_priority": "低优先级",
        "home_context_menu_normal_priority": "普通优先级",
        "home_context_menu_leave": "离开",
        "home_context_menu_mark_as_read": "标为已读",
        "home_context_menu_mark_as_unread": "标为未读",
        "room_event_action_copy": "复制",
        "room_event_action_quote": "引用",
        "room_event_action_remove_poll": "删除投票",
        "room_event_action_end_poll": "结束投票",
        "room_event_action_redact": "移除",
        "room_event_action_more": "更多",
        "room_event_action_share": "分享",
        "room_event_action_forward": "转发",
        "room_event_action_view_in_room": "在房间中查看",
        "room_event_action_permalink": "复制消息链接",
        "room_event_action_view_source": "查看源数据",
        "room_event_action_view_decrypted_source": "查看解密后的源数据",
        "room_event_action_report": "举报内容",
        "room_event_action_report_prompt_reason": "举报此内容的原因",
        "room_event_action_kick_prompt_reason": "移除此用户的原因",
        "room_event_action_ban_prompt_reason": "封禁此用户的原因",
        "room_event_action_report_prompt_ignore_user": "是否隐藏此用户的所有消息？",
        "room_event_action_save": "保存",
        "room_event_action_resend": "重新发送",
        "room_event_action_delete": "删除",
        "room_event_action_delete_confirmation_title": "删除未发送消息",
        "room_event_action_delete_confirmation_message": "确定要删除这条未发送的消息吗？",
        "room_event_action_cancel_send": "取消发送",
        "room_event_action_cancel_download": "取消下载",
        "room_event_action_view_encryption": "加密信息",
        "room_event_action_reply": "回复",
        "room_event_action_reply_in_thread": "消息列",
        "room_event_action_edit": "编辑",
        "room_event_action_reaction_show_all": "显示全部",
        "room_event_action_reaction_show_less": "显示更少",
        "room_event_action_reaction_history": "反应历史",
        "room_event_copy_link_info": "链接已复制到剪贴板。",
        "room_action_camera": "拍照或录像",
        "room_action_send_photo_or_video": "发送照片或视频",
        "room_action_send_sticker": "发送贴纸",
        "room_action_send_file": "发送文件",
        "room_action_reply": "回复",
        "room_action_report": "举报房间",
        "room_action_report_prompt_reason": "举报该房间的原因",
        "room_prompt_resend": "全部重新发送",
        "room_resend_unsent_messages": "重新发送未发送的消息",
        "room_delete_unsent_messages": "删除未发送的消息",
        "room_participants_leave_not_allowed_for_last_owner_msg": "您是该房间唯一的所有者，因此不能离开此房间。",
        "room_participants_action_start_voice_call": "发起语音通话",
        "room_participants_action_start_video_call": "发起视频通话",
        "room_details_favourite_tag": "收藏",
        "room_details_low_priority_tag": "低优先级",
        "room_details_mute_notifs": "静音通知",
        "room_details_direct_chat": "私聊",
        "room_details_copy_room_id": "复制房间 ID",
        "room_details_copy_room_address": "复制房间地址",
        "room_details_copy_room_url": "复制房间链接",
        "room_notifs_settings_done_action": "完成",
        "room_notifs_settings_cancel_action": "取消",
        "room_notifs_settings_manage_notifications": "您可以在 %@ 中管理通知",
        "share_invite_link_action": "分享邀请链接",
        "share_invite_link_room_text": "嗨，加入 %@ 上的这个房间",
        "share_invite_link_space_text": "嗨，加入 %@ 上的这个空间",
        "settings_about": "关于",
        "settings_copyright": "版权",
        "settings_acceptable_use": "可接受使用政策",
        "settings_privacy_policy": "隐私政策",
        "settings_third_party_notices": "第三方通知",
        "settings_mark_all_as_read": "将所有消息标为已读",
        "settings_report_bug": "报告问题",
        "settings_notifications": "通知",
        "settings_device_notifications": "设备通知",
        "settings_direct_messages": "私聊",
        "settings_encrypted_direct_messages": "加密私聊",
        "settings_enable_inapp_notifications": "启用应用内通知",
        "settings_enable_push_notifications": "启用推送通知",
        "settings_notifications_disabled_alert_title": "通知已禁用",
        "settings_notifications_disabled_alert_message": "要启用通知，请前往设备设置。",
        "settings_ui_show_redactions_in_room_history": "为已删除的消息显示占位符",
        "settings_labs_enable_auto_report_decryption_errors": "自动报告解密错误",
        "settings_key_backup_button_delete": "删除备份",
        "settings_key_backup_delete_confirmation_prompt_title": "删除备份",
        "settings_key_backup_delete_confirmation_prompt_msg": "确定吗？如果密钥没有正确备份，您可能会丢失加密消息。",
        "notification_settings_disable_all": "禁用所有通知",
        "notification_settings_enable_notifications": "启用通知",
        "notification_settings_enable_notifications_warning": "当前所有设备上的通知都已被禁用。",
        "notification_settings_global_info": "通知设置会保存到您的账户，并在所有支持的客户端之间共享（包括桌面通知）。\\n\\n规则会按顺序应用；第一条匹配的规则决定消息的通知方式。\\n因此：按关键词通知比按房间通知优先级更高，按房间通知又比按发送者通知优先级更高。\\n同一类型的多条规则中，列表里第一条匹配的规则优先生效。",
        "notification_settings_per_word_notifications": "按关键词通知",
        "notification_settings_per_word_info": "关键词匹配不区分大小写，可以包含 * 通配符。例如：\\nfoo 会匹配由词边界包围的 foo。\\nfoo* 会匹配以 foo 开头的词。\\n*foo* 会匹配包含 foo 的词。",
        "notification_settings_always_notify": "始终通知",
        "notification_settings_never_notify": "从不通知",
        "notification_settings_word_to_match": "要匹配的词",
        "notification_settings_highlight": "高亮",
        "notification_settings_custom_sound": "自定义声音",
        "notification_settings_per_room_notifications": "按房间通知",
        "notification_settings_per_sender_notifications": "按发送者通知",
        "notification_settings_select_room": "选择房间",
        "notification_settings_other_alerts": "其他提醒",
        "notification_settings_contain_my_user_name": "消息包含我的用户名时发出声音通知",
        "notification_settings_contain_my_display_name": "消息包含我的昵称时发出声音通知",
        "notification_settings_just_sent_to_me": "消息只发给我时发出声音通知",
        "notification_settings_invite_to_a_new_room": "我被邀请加入新房间时通知我",
        "notification_settings_people_join_leave_rooms": "有人加入或离开房间时通知我",
        "notification_settings_receive_a_call": "收到通话时通知我",
        "notification_settings_suppress_from_bots": "屏蔽来自机器人的通知",
        "notification_settings_by_default": "默认...",
        "notification_settings_notify_all_other": "通知所有其他消息/房间",
        "onboarding_splash_register_button_title": "注册",
        "onboarding_splash_login_button_title": "我已有账户",
        "onboarding_splash_page_1_title": "掌控您的对话。",
        "onboarding_splash_page_1_message": "安全、独立的沟通方式，让您的交流像面对面一样私密。",
        "onboarding_splash_page_2_title": "一切都在您的掌控中。",
        "onboarding_splash_page_2_message": "选择在哪里保存您的对话，掌控自己的沟通与隐私。通过绽友连接。",
        "onboarding_splash_page_3_title": "安全消息。",
        "onboarding_splash_page_3_message": "端到端加密，无需手机号。没有广告，也不会挖掘您的数据。",
        "onboarding_splash_page_4_title_no_pun": "为团队而生的消息工具。",
        "onboarding_splash_page_4_message": "绽友同样适合团队协作，安全可靠，便于组织沟通。",
        "authentication_registration_title": "创建账户",
        "authentication_registration_username": "用户名",
        "authentication_registration_password_footer": "至少 8 个字符",
        "authentication_login_title": "欢迎回来！",
        "authentication_login_username": "用户名 / 邮箱 / 手机号",
        "authentication_login_forgot_password": "忘记密码",
        "authentication_login_with_qr": "使用二维码登录",
        "authentication_server_selection_login_title": "连接主服务器",
        "authentication_server_selection_login_message": "您的服务器地址是什么？",
        "authentication_server_selection_register_title": "选择主服务器",
        "authentication_server_selection_register_message": "您的服务器地址是什么？这里会保存您的所有数据",
        "authentication_server_selection_server_url": "主服务器 URL",
        "authentication_server_selection_generic_error": "无法在此 URL 找到服务器，请检查地址是否正确。",
        "spaces_add_space": "添加空间",
        "spaces_creation_hint": "空间是一种对房间和联系人分组的新方式。",
        "spaces_creation_visibility_title": "您想创建哪种空间？",
        "spaces_creation_visibility_message": "要加入已有空间，您需要获得邀请。",
        "spaces_creation_footer": "您之后可以更改",
        "spaces_creation_address": "地址",
        "spaces_creation_empty_room_name_error": "需要名称",
        "spaces_creation_public_space_title": "您的公开空间",
        "spaces_creation_private_space_title": "您的私密空间",
        "spaces_creation_cancel_title": "停止创建空间？",
        "spaces_creation_cancel_message": "您的进度将会丢失。",
        "spaces_creation_new_rooms_title": "您会讨论哪些话题？",
        "spaces_creation_new_rooms_message": "我们会为每个话题创建一个房间。",
        "spaces_creation_new_rooms_room_name_title": "房间名称",
        "spaces_creation_new_rooms_general": "常规",
        "spaces_creation_new_rooms_random": "闲聊",
        "spaces_creation_new_rooms_support": "支持",
        "spaces_creation_invite_by_username": "通过用户名邀请",
        "spaces_creation_post_process_creating_space": "正在创建空间",
        "spaces_creation_post_process_creating_space_task": "正在创建 %@",
        "spaces_creation_post_process_uploading_avatar": "正在上传头像",
        "spaces_creation_post_process_creating_room": "正在创建 %@",
        "spaces_creation_post_process_adding_rooms": "正在添加 %@ 个房间",
        "spaces_creation_post_process_inviting_users": "正在邀请 %@ 个用户",
        "space_settings_current_address_message": "这个空间可通过以下地址访问\\n%@",
        "leave_space_action": "离开空间",
        "leave_space_and_one_room": "离开空间和 1 个房间",
        "leave_space_and_more_rooms": "离开空间和 %@ 个房间",
        "leave_space_selection_title": "选择房间",
        "leave_space_selection_all_rooms": "选择所有房间",
        "leave_space_selection_no_rooms": "不选择任何房间",
        "location_sharing_settings_header": "位置共享",
        "location_sharing_settings_toggle_title": "启用位置共享",
        "location_sharing_static_share_title": "发送我的当前位置",
        "location_sharing_pin_drop_share_title": "发送此位置",
        "user_session_push_notifications": "推送通知",
        "user_session_push_notifications_message": "开启后，此会话将接收推送通知。",
    }

    for path, text in [(zh_path, zh_text), (en_path, en_text)]:
        text = apply_strings_overrides(text, overrides, base_keys)
        text = apply_brand_wording(text)
        write(path, text)


def icon_pixels(size: str, scale: str) -> int:
    width = float(size.split("x", 1)[0])
    multiplier = int(scale.rstrip("x"))
    return round(width * multiplier)


def resize_icon(source: Path, destination: Path, pixels: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["sips", "-z", str(pixels), str(pixels), str(source), "--out", str(destination)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def patch_app_icon() -> None:
    if not ICON_SOURCE.exists():
        raise RuntimeError(f"Brand icon not found: {ICON_SOURCE}")

    app_icon_dirs = [
        ROOT / "Riot" / "Assets" / "SharedImages.xcassets" / "AppIcon.appiconset",
        ROOT / "Variants" / "Alpha" / "Riot" / "Assets" / "SharedImages.xcassets" / "AppIcon.appiconset",
    ]
    patched_dirs = 0
    generated_files = 0

    for app_icon_dir in app_icon_dirs:
        contents_json = app_icon_dir / "Contents.json"
        if not contents_json.exists():
            continue

        contents = json.loads(read(contents_json))
        for image in contents.get("images", []):
            filename = image.get("filename")
            size = image.get("size")
            scale = image.get("scale")
            if not filename or not size or not scale:
                continue
            pixels = icon_pixels(size, scale)
            resize_icon(ICON_SOURCE, app_icon_dir / filename, pixels)
            generated_files += 1
        patched_dirs += 1

    if patched_dirs == 0:
        raise RuntimeError("Could not locate AppIcon.appiconset")

    print(f"App icon patched from {ICON_SOURCE}")
    print(f"App icon sets patched: {patched_dirs}, generated PNGs: {generated_files}")


def copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        raise RuntimeError(f"Missing branding asset: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def write_asset_contents(path: Path, filename: str) -> None:
    contents = {
        "images": [
            {
                "filename": filename,
                "idiom": "universal",
                "scale": "1x",
            }
        ],
        "info": {
            "author": "xcode",
            "version": 1,
        },
    }
    path.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")


def patch_brand_artwork() -> None:
    if not ONBOARDING_ASSETS_DIR.exists():
        raise RuntimeError(f"Brand artwork directory not found: {ONBOARDING_ASSETS_DIR}")

    onboarding_targets = [
        ("onboarding_splash_screen_page_1.imageset", "zhanyou_onboarding_splash_page_1.png"),
        ("onboarding_splash_screen_page_1_dark.imageset", "zhanyou_onboarding_splash_page_1_dark.png"),
        ("onboarding_splash_screen_page_2.imageset", "zhanyou_onboarding_splash_page_2.png"),
        ("onboarding_splash_screen_page_2_dark.imageset", "zhanyou_onboarding_splash_page_2_dark.png"),
        ("onboarding_splash_screen_page_3.imageset", "zhanyou_onboarding_splash_page_3.png"),
        ("onboarding_splash_screen_page_3_dark.imageset", "zhanyou_onboarding_splash_page_3_dark.png"),
        ("onboarding_splash_screen_page_4.imageset", "zhanyou_onboarding_splash_page_4.png"),
        ("onboarding_splash_screen_page_4_dark.imageset", "zhanyou_onboarding_splash_page_4_dark.png"),
    ]
    for image_set, source_name in onboarding_targets:
        image_set_dir = ROOT / "Riot" / "Assets" / "Images.xcassets" / "Onboarding" / image_set
        copy_file(ONBOARDING_ASSETS_DIR / source_name, image_set_dir / source_name)
        write_asset_contents(image_set_dir / "Contents.json", source_name)

    empty_targets = [
        (
            "all_chats_empty_screen_artwork.imageset",
            "zhanyou_all_chats_empty_screen_artwork",
            "all_chats_empty_screen_artwork",
        ),
        (
            "all_chats_empty_screen_artwork_dark.imageset",
            "zhanyou_all_chats_empty_screen_artwork_dark",
            "all_chats_empty_screen_artwork_dark",
        ),
    ]
    for image_set, source_prefix, destination_prefix in empty_targets:
        image_set_dir = ROOT / "Riot" / "Assets" / "Images.xcassets" / "Home" / image_set
        for suffix in ["", "@2x", "@3x"]:
            copy_file(
                ONBOARDING_ASSETS_DIR / f"{source_prefix}{suffix}.png",
                image_set_dir / f"{destination_prefix}{suffix}.png",
            )

    list_placeholder_dir = (
        ROOT
        / "Riot"
        / "Assets"
        / "Images.xcassets"
        / "Home"
        / "all_chats_empty_list_placeholder_icon.imageset"
    )
    copy_file(
        ONBOARDING_ASSETS_DIR / "zhanyou_empty_list_placeholder_icon.png",
        list_placeholder_dir / "zhanyou_empty_list_placeholder_icon.png",
    )
    write_asset_contents(list_placeholder_dir / "Contents.json", "zhanyou_empty_list_placeholder_icon.png")

    print("Brand onboarding and empty-state artwork patched")


def patch_third_party_signing_runtime() -> None:
    """Avoid runtime entitlements that third-party signing services usually cannot provide."""
    replacements = {
        ROOT / "Riot" / "Managers" / "EncryptionKeyManager" / "EncryptionKeyManager.swift": [
            (
                "KeychainStore(withKeychain: Keychain(service: keychainService, accessGroup: BuildSettings.keychainAccessGroup))",
                "KeychainStore(withKeychain: Keychain(service: keychainService))",
                "encryption keychain access group",
            ),
        ],
        ROOT / "Riot" / "Managers" / "PushNotification" / "PushNotificationStore.swift": [
            (
                "KeychainStore(withKeychain: Keychain(service: PushNotificationConstants.pushNotificationKeychainService,\n                                                     accessGroup: BuildSettings.keychainAccessGroup))",
                "KeychainStore(withKeychain: Keychain(service: PushNotificationConstants.pushNotificationKeychainService))",
                "push notification keychain access group",
            ),
        ],
        ROOT / "Riot" / "Modules" / "SetPinCode" / "PinCodePreferences.swift": [
            (
                "KeychainStore(withKeychain: Keychain(service: PinConstants.pinCodeKeychainService,\n                                                     accessGroup: BuildSettings.keychainAccessGroup))",
                "KeychainStore(withKeychain: Keychain(service: PinConstants.pinCodeKeychainService))",
                "pin keychain access group",
            ),
        ],
        ROOT / "Riot" / "Managers" / "Settings" / "RiotSettings.swift": [
            (
                "static var defaults: UserDefaults = {\n        guard let userDefaults = UserDefaults(suiteName: BuildSettings.applicationGroupIdentifier) else {\n            fatalError(\"[RiotSettings] Fail to load shared UserDefaults\")\n        }\n        return userDefaults\n    }()",
                "static var defaults: UserDefaults = {\n        UserDefaults(suiteName: BuildSettings.applicationGroupIdentifier) ?? UserDefaults.standard\n    }()",
                "RiotSettings app group fallback",
            ),
        ],
        ROOT / "Riot" / "Modules" / "MatrixKit" / "Models" / "MXKAppSettings.m": [
            (
                "sharedUserDefaults = [[NSUserDefaults alloc] initWithSuiteName:_currentApplicationGroup];",
                "sharedUserDefaults = [[NSUserDefaults alloc] initWithSuiteName:_currentApplicationGroup];\n        if (!sharedUserDefaults)\n        {\n            sharedUserDefaults = [NSUserDefaults standardUserDefaults];\n        }",
                "MatrixKit shared defaults fallback",
            ),
        ],
    }

    for path, path_replacements in replacements.items():
        text = read(path)
        for old, new, label in path_replacements:
            text = replace_literal(text, old, new, label)
        write(path, text)


def main() -> None:
    if not ROOT.exists():
        raise SystemExit(f"Element iOS directory not found: {ROOT}")
    patch_build_settings()
    patch_settings_about_buttons()
    patch_app_identifiers()
    patch_project_keychain_group()
    patch_language()
    patch_localized_strings()
    patch_app_icon()
    patch_brand_artwork()
    patch_third_party_signing_runtime()
    print(f"Patched Element iOS for {APP_NAME}")
    print(f"Homeserver: {HOMESERVER}")
    print(f"Permalink: {WEB_URL}")
    print(f"Bundle ID: {BASE_BUNDLE_ID}")
    print(f"Language: {LANGUAGE}")
    print("Third-party signing runtime: custom app/keychain groups disabled")


if __name__ == "__main__":
    main()
