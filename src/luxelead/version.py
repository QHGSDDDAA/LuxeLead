"""Application version and online-update configuration."""

VERSION = "0.8.1"
DISPLAY_VERSION = "测试版V0.8.1"
RELEASE_DATE = "2026-07-22"

# GitLab Generic Package URL for update manifest (private repo; requires deploy token).
# GitHub Releases URL for update checking (public).
GITHUB_RELEASES_URL = "https://github.com/QHGSDDDAA/LuxeLead/releases/latest"
GITHUB_API_RELEASES_URL = (
    "https://api.github.com/repos/QHGSDDDAA/LuxeLead/releases/latest"
)

# GitLab Generic Package URL for update manifest (private repo; requires deploy token).
# Only used for Windows internal-network updates.
DEFAULT_MANIFEST_URL = GITHUB_API_RELEASES_URL

# Read-only deploy token (read_package_registry). Override via ~/.luxelead/config.json.
UPDATE_DEPLOY_TOKEN = ""
