# 拾句 Privacy

拾句 (formerly English Studio) stores articles, progress, practice history, translations, audio caches and FSRS data locally. The Windows data directory remains `%LOCALAPPDATA%\EnglishStudio`; the macOS directory is `~/Library/Application Support/EnglishStudio/`. Windows legacy data is copied only when the current directory has no database, and the legacy directory is retained.

DeepSeek, MiniMax and Free Dictionary are optional online services. Configured translation, proofreading, vocabulary and AI read-aloud features send the necessary text to their provider. Cached content can be reused offline. The current product does not offer user recording, dictation or Azure pronunciation scoring; legacy database tables remain for upgrade compatibility.

Keys are stored in Windows Credential Manager or the native macOS Keychain, not in SQLite, ordinary settings, logs or source control. Builds contain no user credentials or databases. Removing the application leaves user data and credentials in place. Back up the full data directory while the application is closed so that SQLite WAL/SHM files are included when present. Credentials must be configured again when moving to another operating system.
