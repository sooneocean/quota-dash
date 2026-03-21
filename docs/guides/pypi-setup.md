# PyPI Publishing Setup

## Prerequisites

- A PyPI account at [pypi.org](https://pypi.org)
- Owner access to the GitHub repo `sooneocean/quota-dash`

## Steps

### 1. Create the PyPI Project

If the package hasn't been published yet, you need to create it first:

```bash
cd quota-dash
pip install build twine
python3 -m build
twine upload dist/*
```

You'll be prompted for your PyPI username and password (or API token).

### 2. Configure Trusted Publisher

Once the project exists on PyPI:

1. Go to [pypi.org/manage/project/quota-dash/settings/publishing/](https://pypi.org/manage/project/quota-dash/settings/publishing/)
2. Under "Add a new publisher", fill in:
   - **Owner**: `sooneocean`
   - **Repository name**: `quota-dash`
   - **Workflow name**: `release.yml`
   - **Environment name**: (leave blank)
3. Click "Add"

### 3. Test the Release

```bash
# Create a test tag
git tag v1.0.1
git push --tags
```

The `release.yml` workflow will:
1. Build the package
2. Upload to PyPI via OIDC (no token needed)
3. Create a GitHub Release

### 4. Verify

- Check [pypi.org/project/quota-dash/](https://pypi.org/project/quota-dash/)
- Test install: `pip install quota-dash`

## Troubleshooting

- **"No matching publisher"**: Verify the workflow name is exactly `release.yml`
- **"Project not found"**: You must upload manually first before configuring trusted publishing
- **Build fails**: Run `python3 -m build` locally to debug
