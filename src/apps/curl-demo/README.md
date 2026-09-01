# Curl through the Coil C reader

This self-contained project vendors upstream curl and compiles its C translation
units through the Coil C reader. No generated Coil source or shell wrapper is
checked in: importing the mapped public header runs the reader from `Coil.toml`.

Run the libcurl API demo:

```sh
coil run
```

Run the complete curl command-line client:

```sh
coil run cli.coil -- --version
coil run cli.coil -- https://example.com/
```

The default optimization level is `-O2`. The vendored source revision is recorded
in `vendor/curl.commit`; `target/darwin-arm64` contains CMake-generated platform
configuration and curl's generated manual source for that exact revision.
