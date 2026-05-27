#!/usr/bin/env python3
import os
import re
from pathlib import Path

ROOT = Path(os.environ.get("ELEMENT_IOS_DIR", "element-ios"))
HOMESERVER = "https://matrix.vudo-app.top"
SERVER_NAME = "matrix.vudo-app.top"
WEB_URL = "https://element.vudo-app.top"
APP_NAME = "Vudo"
BASE_BUNDLE_ID = "top.vudo.app"
APP_GROUP_ID = ""
APP_SCHEME = "vudo"
LANGUAGE = "zh-Hans"


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
    if old not in text:
        raise RuntimeError(f"Could not patch {label}")
    return text.replace(old, new, 1)


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
        'static let stunServerFallbackUrlString: String? = "stun:turn.vudo-app.top:3478"',
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
            + "        UserDefaults.standard.synchronize()\n"
        )
        if marker not in text:
            raise RuntimeError("Could not locate AppDelegate willFinishLaunchingWithOptions")
        text = text.replace(marker, insert, 1)
        write(app_delegate, text)


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
    patch_app_identifiers()
    patch_project_keychain_group()
    patch_language()
    patch_third_party_signing_runtime()
    print("Patched Element iOS for Vudo")
    print(f"Homeserver: {HOMESERVER}")
    print(f"Permalink: {WEB_URL}")
    print(f"Bundle ID: {BASE_BUNDLE_ID}")
    print(f"Language: {LANGUAGE}")
    print("Third-party signing runtime: custom app/keychain groups disabled")


if __name__ == "__main__":
    main()
