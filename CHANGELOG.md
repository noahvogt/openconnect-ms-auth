## v1.0.0 (2026-10-03)

## v0.6.0 (2026-09-30)

### Feat

- skip the login by reusing an earlier session

## v0.5.0 (2026-09-30)

### Feat

- massively improve performance by racing the expected elements against the error ones

## v0.4.2 (2026-09-30)

### Fix

- wait for the webvpn cookie instead of the install page The portal only shows the Cisco provisioning page on some logins, so requiring it made every other login fail even though the cookie was already set. Poll for the cookie instead, and return to the VPN domain once if it is not readable from wherever the login ended up.

## v0.4.1 (2026-09-30)

### Feat

- resolve credentials outside of the command line

## [0.3.2](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/compare/0.3.1...0.3.2) (2024-10-29)

### Bug Fixes

- Change case of readme ([01029d1](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/commit/01029d1beefe471830f4f6d2ac50c1dc6c3eee09))

## [0.3.1](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/compare/0.3.0...0.3.1) (2024-10-29)

### Bug Fixes

- Install instructions ([aee4fd8](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/commit/aee4fd8ab5dfaf096843be4bdfb9348ec6fb3d35))

# [0.3.0](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/compare/0.2.0...0.3.0) (2023-08-08)

### Features

- Additional checks if login is valid ([3595059](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/commit/3595059addf604a6ea5c433c90304bcf265be4f0))

# [0.2.0](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/compare/0.1.5...0.2.0) (2023-05-10)

### Features

- Change auth method if defaults to MS-Authenticator ([02d5ac3](https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth/commit/02d5ac341b54b6d2011216a99f082334997539da))
