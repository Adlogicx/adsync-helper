name: Build AdSync Helper APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build-apk:
    runs-on: ubuntu-22.04
    timeout-minutes: 60

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python 3.10
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - name: Cache buildozer
        uses: actions/cache@v3
        with:
          path: ~/.buildozer
          key: buildozer-${{ hashFiles('buildozer.spec') }}
          restore-keys: buildozer-

      - name: Install system dependencies
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y \
            git zip unzip openjdk-17-jdk \
            autoconf libtool pkg-config \
            zlib1g-dev libffi-dev libssl-dev cmake

      - name: Set up Android SDK and accept licences
        run: |
          sudo apt-get install -y wget
          wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
          mkdir -p $HOME/android-sdk/cmdline-tools
          unzip -q commandlinetools-linux-11076708_latest.zip -d $HOME/android-sdk/cmdline-tools
          mv $HOME/android-sdk/cmdline-tools/cmdline-tools $HOME/android-sdk/cmdline-tools/latest
          echo "ANDROID_SDK_ROOT=$HOME/android-sdk" >> $GITHUB_ENV
          echo "ANDROID_HOME=$HOME/android-sdk" >> $GITHUB_ENV
          echo "$HOME/android-sdk/cmdline-tools/latest/bin" >> $GITHUB_PATH
          echo "$HOME/android-sdk/platform-tools" >> $GITHUB_PATH
          yes | $HOME/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses
          $HOME/android-sdk/cmdline-tools/latest/bin/sdkmanager \
            "platform-tools" \
            "build-tools;34.0.0" \
            "platforms;android-34"

      - name: Install buildozer + cython
        run: pip install buildozer cython==0.29.36

      - name: Build debug APK
        run: buildozer android debug
        env:
          ANDROID_SDK_ROOT: ${{ env.ANDROID_SDK_ROOT }}
          ANDROID_HOME: ${{ env.ANDROID_HOME }}

      - name: Rename APK
        run: |
          mkdir -p output
          cp bin/*.apk output/AdSyncHelper.apk

      - name: Upload APK artifact
        uses: actions/upload-artifact@v3
        with:
          name: AdSyncHelper-debug
          path: output/AdSyncHelper.apk
          retention-days: 30

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v1.0-build-${{ github.run_number }}
          name: "AdSync Helper — Build #${{ github.run_number }}"
          body: |
            Download AdSyncHelper.apk below and install on Android.
          files: output/AdSyncHelper.apk
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
