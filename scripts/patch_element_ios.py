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
    patch_app_icon()
    patch_third_party_signing_runtime()
    print(f"Patched Element iOS for {APP_NAME}")
    print(f"Homeserver: {HOMESERVER}")
    print(f"Permalink: {WEB_URL}")
    print(f"Bundle ID: {BASE_BUNDLE_ID}")
    print(f"Language: {LANGUAGE}")
    print("Third-party signing runtime: custom app/keychain groups disabled")


if __name__ == "__main__":
    main()
