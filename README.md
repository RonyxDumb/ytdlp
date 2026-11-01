# YtDlp · Android e Windows

**By Francesco Pio Pipino**

Un'interfaccia in italiano per scaricare un video alla volta con yt-dlp.

| Piattaforma | Sorgenti e istruzioni | Requisiti |
| --- | --- | --- |
| Windows | [windows/](windows/README.md) | Windows 10/11 a 64 bit |
| Android | [android/](android/README.md) | Android 10 o successivo |

## Windows

Apri le [release](https://github.com/RonyxDumb/ytdlp/releases), scarica **YtDlp-Windows-x64.zip** dalla release `windows-v…`, estrai la cartella e avvia **YtDlp.exe**. Non serve installare Python per usare l'eseguibile.

Incolla l'indirizzo nella barra, scegli **Formato del download** e premi **Scarica video** oppure **Scarica audio**. Sotto compaiono progresso, velocità e tempo rimasto. Puoi annullare, scegliere la cartella e aprirla direttamente. Destinazione iniziale: `Download/YtDlp`.

Su entrambe le piattaforme puoi scegliere **MP4, MKV, WebM, video automatico, MP3, WAV, M4A, FLAC, Opus e OGG Vorbis**. L'app ricorda l'ultima scelta. I formati audio estraggono solo la traccia audio e FFmpeg converte quando necessario; WAV e FLAC non migliorano la qualità della sorgente. Le conversioni video possono richiedere tempo. Il completamento viene mostrato dopo la finalizzazione del file.

Al primo download l'app prepara yt-dlp, FFmpeg e Deno dalle loro release ufficiali, verificando il digest SHA-256. Gli avvii successivi riutilizzano gli strumenti già preparati. Per aggiornare gli estrattori: **Impostazioni → Aggiorna motore yt-dlp e strumenti**.

La verifica delle nuove versioni dell'app parte all'avvio ed è disponibile anche con **Verifica aggiornamenti**. Una nuova release Windows mostra **Aggiorna app**: scarica il pacchetto, verifica SHA-256 e, dopo la tua scelta, sostituisce l'eseguibile e riapre l'app. Conserva una copia della versione precedente e mantiene impostazioni e download.

Il repository `RonyxDumb/ytdlp` è pubblico: **gli aggiornamenti funzionano senza token**. Se in futuro diventa privato, puoi inserire in **Impostazioni** un fine-grained token GitHub limitato a questo repository, con `Contents: Read-only`. Il token resta nel Gestore credenziali di Windows e non viene inserito nei sorgenti, negli eseguibili o nelle impostazioni JSON.

## Android

Il progetto Android 1.3 completo è in [`android/`](android/). Apri questa cartella in Android Studio oppure esegui `android/docker_build.bat` con Docker Desktop. L'APK appare in `android/output/YtDlp.apk`. Da terminale: `cd android` e `./gradlew testDebugUnitTest assembleDebug`.

## Compilazione automatica

- **Windows:** ogni modifica a `windows/` su `main` esegue test, un piccolo download da server locale, verifica l'interfaccia e genera lo ZIP portatile. Una versione nuova viene pubblicata nelle release con tag `windows-vX.Y.Z`.
- **Android:** ogni modifica a `android/` verifica i test esistenti e produce un APK negli artefatti della run.
- Per una nuova release Windows cambia `VERSION` in `windows/ytdlp_windows/__init__.py` e aggiorna `windows/RELEASE_NOTES.md`. Una release già pubblicata non viene sovrascritta.

I siti disponibili dipendono dagli estrattori e dal resolver: la presenza dell'interfaccia non garantisce il funzionamento di ogni servizio. Il resolver Android 1.2 per le pagine pubbliche StreamingCommunity/VixCloud è presente anche su Windows. Non gestisce login o DRM. Usa solo contenuti che puoi scaricare.
