# LDView headless — command-line LDraw renderer (EGL build).
#
# Builds the OSMesa/EGL target from https://github.com/tcobbs/ldview which
# produces a single `ldview` binary that can render LDraw models to PNG/BMP/JPG
# without a display server.  Uses EGL + llvmpipe (software) for off-screen
# rendering — OSMesa is no longer available in Mesa ≥ 25.
#
# The LDraw parts library (complete.zip) is bundled so that ldview can resolve
# standard parts out of the box.
{
  lib,
  stdenv,
  fetchFromGitHub,
  fetchurl,
  mesa,
  libGL,
  libGLU,
  libjpeg,
  libpng,
  zlib,
  makeWrapper,
}:
let
  # LDraw complete parts library — needed at runtime to resolve part files.
  ldrawLibrary = fetchurl {
    url = "https://library.ldraw.org/library/updates/complete.zip";
    hash = "sha256-1qn+MMDVQqNv6w375jw/0uziKs3os5aB2iF0ii+d71s=";
    name = "ldraw-complete.zip";
  };
in
stdenv.mkDerivation rec {
  pname = "ldview";
  version = "4.7";

  src = fetchFromGitHub {
    owner = "tcobbs";
    repo = "ldview";
    rev = "v${version}";
    hash = "sha256-9AeSmoUpNT9tP/e9Anw49Bmmf3i1Z+7FjsmOXIEEwQQ=";
  };

  nativeBuildInputs = [ makeWrapper ];
  buildInputs = [
    mesa
    libGL
    libGLU
    libjpeg
    libpng
    zlib
  ];

  # --- patch phase ---------------------------------------------------------
  # LDView's OSMesa Makefile always enables EGL (headless rendering).  OSMesa
  # support is optional and detected by checking /usr/include — which doesn't
  # exist in Nix.  We leave the OSMesa detection alone (it'll be negative, no
  # problem) since EGL is sufficient.
  # No patches needed: the Nix compiler wrapper injects include/lib paths for
  # all buildInputs automatically.

  # --- build phase ----------------------------------------------------------
  buildPhase = ''
    runHook preBuild
    make -C OSMesa -j$NIX_BUILD_CORES
    runHook postBuild
  '';

  # --- install phase --------------------------------------------------------
  installPhase = ''
    runHook preInstall

    mkdir -p $out/bin $out/share/ldraw

    cp OSMesa/ldview $out/bin/ldview

    # Bundle LDraw parts library
    cp ${ldrawLibrary} $out/share/ldraw/complete.zip

    # Wrap the binary so it always finds the LDraw library and never tries to
    # phone home for missing parts.
    wrapProgram $out/bin/ldview \
      --add-flags "-LDrawZip=$out/share/ldraw/complete.zip" \
      --add-flags "-CheckPartTracker=0"

    runHook postInstall
  '';

  meta = with lib; {
    description = "Headless command-line LDraw model renderer (EGL build)";
    homepage = "https://github.com/tcobbs/ldview";
    license = with licenses; [
      gpl2Only
      mit
    ];
    maintainers = [ ];
    platforms = platforms.linux;
    mainProgram = "ldview";
  };
}
