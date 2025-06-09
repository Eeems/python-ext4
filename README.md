[![ext4 on PyPI](https://img.shields.io/pypi/v/ext4)](https://pypi.org/project/ext4)

# Ext4
Library for read only interactions with an ext4 filesystem.

```python
from ext4 import Volume

# Extract raw ext4 image
with open("image.ext4", "rb") as f:
    # Extract specific file
    volume = Volume(f, offset=0)
    inode = volume.inode_at("/etc/version")
    with open("version", "wb") as f:
        f.write(inode.open().read())
```
