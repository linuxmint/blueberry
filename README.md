## Introduction

A wrapper application to use gnome-bluetooth outside of GNOME.

Depends on gnome-bluetooth >= 3.14 and <= 41.

---

## How to build and install

#### Download the source code and enter the source directory

```
# Clone this repo:
git clone https://github.com/linuxmint/blueberry.git

# Enter the folder:
cd blueberry
```

#### Building the package

```
# Use mint-build to build the project for the first time.
# This also fetches and installs the build dependencies:
mint-build

# In subsequent builds, you can use dpkg-buildpackage for faster builds:
dpkg-buildPackage
```

#### Install the package:

```
# Once that succeeds, install:
cd ..
sudo dpkg -i blueberry\*.deb
```

For more information, refer the developer guide:
https://linuxmint-developer-guide.readthedocs.io/en/latest/index.html
