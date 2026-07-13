# English Studio Privacy

English Studio stores articles, progress, practice history, FSRS data and optional pronunciation records locally. The default current data directory is `%LOCALAPPDATA%\EnglishStudio`; existing `%LOCALAPPDATA%\EnglishTypingTrainer` data is copied only when the new directory has no database, and the old directory is retained.

DeepSeek, MiniMax and Azure Speech are optional. Text or audio is sent only after the user invokes the relevant online feature and configures its credential. Azure pronunciation scoring is Beta; recordings are temporary by default and are removed after cancellation or scoring. Users can choose to retain a recording, then delete the matching history record to remove its local file.

Keys are stored in Windows Credential Manager, not in SQLite, ordinary settings, logs or source control. Back up the full data directory while the application is closed so that SQLite WAL/SHM files are included when present.
