# Zhanyou Element iOS unsigned build

This repository builds a customized unsigned IPA from Element Classic iOS using GitHub Actions.

- Brand: 绽友
- Homeserver: https://matrix.xuyoxxx.com
- Output: unsigned IPA for third-party signing
- Signing: disabled during build; final IPA is cleaned before upload
- Icon: generated from `branding/zhan-you-icon-1024.png`
- Onboarding and empty-state artwork: replaced with Zhanyou assets
- Default room timeline style: message bubbles enabled

Run **Actions -> Build unsigned iOS IPA -> Run workflow** to build manually. Pushes to `main` that change the workflow, patch script, README, or icon also trigger a build.
