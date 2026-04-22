**dataset collector**

building a Docker image:
```sh
docker build -t dataset-builder .
```

import projects:
```sh
docker run --rm \
  -v $(pwd)/dataset_sources:/app/dataset_sources \
  -e GITHUB_TOKEN="${GITHUB_TOKEN:-}" \
  dataset-builder python3 scripts/find_projects.py
```

compile projects:
```sh
docker run --rm \
  -v $(pwd)/dataset_sources:/app/dataset_sources \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/scripts:/app/scripts \
  dataset-builder bash /app/scripts/build.sh
```

all of this can be automatically done by workflow(start workflow)
