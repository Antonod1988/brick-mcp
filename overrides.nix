# Python package overrides shared between flake.nix and devenv.nix
final: prev: {
  "hatchling" = prev."hatchling".overrideAttrs (old: {
    propagatedBuildInputs = [ final."editables" ];
  });
  "cairocffi" = prev."cairocffi".overrideAttrs (old: {
    postInstall =
      let
        isDarwin = final.pkgs.stdenv.hostPlatform.isDarwin;
        cairoLib =
          if isDarwin then
            "${final.pkgs.cairo}/lib/libcairo.2.dylib"
          else
            "${final.pkgs.cairo}/lib/libcairo.so.2";
      in
      (old.postInstall or "") + ''
        substituteInPlace $out/lib/python*/site-packages/cairocffi/__init__.py \
          --replace-fail \
            "('libcairo.so.2', 'libcairo.2.dylib', 'libcairo-2.dll')" \
            "('${cairoLib}', 'libcairo.so.2', 'libcairo.2.dylib', 'libcairo-2.dll')"
      '';
  });
}
