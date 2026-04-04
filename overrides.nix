# Python package overrides shared between flake.nix and devenv.nix
final: prev: {
  "hatchling" = prev."hatchling".overrideAttrs (old: {
    propagatedBuildInputs = [ final."editables" ];
  });
}
