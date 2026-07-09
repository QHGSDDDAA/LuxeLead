"""Application version and online-update configuration."""

VERSION = "0.8.0"
DISPLAY_VERSION = "测试版V0.8.0"
RELEASE_DATE = "2026-06-30"

# GitLab Generic Package URL for update manifest (private repo; requires deploy token).
DEFAULT_MANIFEST_URL = (
    "http://10.8.251.3:8081/api/v4/projects/220/packages/generic/"
    "luxelead-manifest/latest/version.json"
)

# Read-only deploy token (read_package_registry). Override via ~/.luxelead/config.json.
UPDATE_DEPLOY_TOKEN = "TAbeoRd3JNc76j9UGipw"
