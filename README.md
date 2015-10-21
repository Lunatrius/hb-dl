## Humble Bundle Downloader
Humble Bundle Downloader is a *simple* Python script that can download most of the DRM free content from your Humble Bundle Library.

### Usage
```
# refresh download tokens
hbdl.py -r

# downloads all audio files that contains bastion in the name
hbdl.py -p audio -d bastion

# downloads all nightsky files that are for windows OR linux
hbdl.py -p windows linux -d nightsky

# downloads all nightsky AND "the swapper" files
hbdl.py -d nightsky "the swapper"
```
