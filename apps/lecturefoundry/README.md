# LectureFoundry Reader

A native Flutter reader for LectureFoundry's generated `lesson.json` files.
It connects directly to an HTTPS WebDAV provider—there is no app backend and no
provider-specific SDK.

## What it does

- Discovers courses, numbered modules, numbered lectures, and study patterns.
- Renders revision, deep-dive, active-recall, and concept-map notes natively.
- Uses an adaptive layout for Android, iPhone, iPad, macOS, Windows, and Linux.
- Stores WebDAV credentials in Keychain, Android Keystore-backed storage,
  Windows credential storage, or Linux Secret Service.
- Caches opened `lesson.json` files and falls back to the cached copy when a
  download temporarily fails.
- Lets users mark lectures as read and syncs those ticks between devices using
  a small course-level WebDAV metadata file. Offline changes sync later.

## Cloud folder structure

Choose a root folder such as `/Our Project/`. Every course inside it must use
the output layout produced by LectureFoundry:

```text
Our Project/
├── Course 1/
│   ├── .lecturefoundry-progress.json
│   └── 01-module-name/
│       └── 01-lecture-name/
│           ├── revision/lesson.json
│           ├── deep-dive/lesson.json
│           ├── active-recall/lesson.json
│           └── concept-map/lesson.json
└── Course 2/
    └── ...
```

Folder names for modules and lectures must begin with a number followed by a
hyphen, underscore, or space. Extra files such as `index.html`, `source.json`,
and `generation.json` are safely ignored.

The reader creates `.lecturefoundry-progress.json` automatically after a
lecture is marked read or unread. It contains only lecture-relative paths,
boolean read states, and update timestamps—never WebDAV credentials or lesson
content. A timestamped device cache keeps progress usable offline and merges it
back into this course file after connectivity returns.

## Connect to Koofr

Create a Koofr app password, then enter these values on the connection screen:

```text
WebDAV endpoint:    https://app.koofr.net/dav/Koofr/
Username:           your Koofr account email
WebDAV app password: your generated app password
Library root:       /Our Project/
```

`Koofr` is case-sensitive. Using the broader endpoint
`https://app.koofr.net/dav/` also works if the library root is entered as
`/Koofr/Our Project/`.

Do not add a username or password to Dart source, configuration files, build
arguments, screenshots, or Git. The app accepts them only at runtime and stores
them with `flutter_secure_storage`. Use an app-specific password rather than
your main account password whenever the provider supports one.

Other providers work when they expose a standards-compatible WebDAV endpoint
over HTTPS. HTTP is rejected except for `localhost` development servers.

## Run and test

Install the Flutter stable SDK, then from this directory run:

```bash
flutter pub get
flutter analyze
flutter test
flutter run
```

Useful target commands include:

```bash
flutter run -d macos
flutter run -d windows
flutter run -d linux
flutter build apk
flutter build ios
```

Android release builds are deliberately unsigned unless a private signing
configuration is supplied. Copy `android/key.properties.example` to
`android/key.properties`, point it at your upload keystore, and replace the
placeholder values. Both the real properties file and keystore files are
ignored by Git. Never distribute a release signed with Android's debug key.

Apple device distribution builds need the usual Xcode signing team. macOS uses
the classic Keychain API so local ad-hoc builds can store credentials securely
without a provisioning profile; iOS device builds still use Xcode signing.

Android secure storage requires API 23 or later; the effective app minimum is
the value supplied by the installed Flutter SDK. On Windows, install Visual
Studio's C++ desktop workload and C++ ATL. On Debian/Ubuntu Linux, install the
GTK and Libsecret development dependencies:

```bash
sudo apt install clang cmake ninja-build pkg-config libgtk-3-dev \
  libsecret-1-0 libsecret-1-dev
```

## Architecture

```text
lib/
├── models/       WebDAV settings and lesson schema
├── services/     credential storage, WebDAV transport, discovery, cache
├── screens/      connection, library navigation, native lesson reader
└── widgets/      reusable responsive UI components
```

`WebDavDataSource` keeps remote I/O replaceable and testable. The repository
understands the LectureFoundry folder convention, while the screens know only
about typed course and lesson models.
