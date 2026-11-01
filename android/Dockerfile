FROM eclipse-temurin:17-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*
ENV ANDROID_HOME=/opt/android-sdk
RUN mkdir -p $ANDROID_HOME/cmdline-tools && curl -fL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/sdk.zip && unzip -q /tmp/sdk.zip -d $ANDROID_HOME/cmdline-tools && mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest && rm /tmp/sdk.zip
RUN yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null
RUN $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager 'platforms;android-35' 'build-tools;35.0.0'
RUN curl -fL https://services.gradle.org/distributions/gradle-8.11.1-bin.zip -o /tmp/gradle.zip && unzip -q /tmp/gradle.zip -d /opt && rm /tmp/gradle.zip
ENV PATH=/opt/gradle-8.11.1/bin:$PATH
WORKDIR /src
CMD ["bash", "build_android.sh"]
