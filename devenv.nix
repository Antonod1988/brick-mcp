let
  shell =
    { pkgs, ... }:
    {
      imports = [
        ./devenv.uv2nix.nix
      ];

      languages.python.interpreter = pkgs.python314;
      languages.python.pyprojectOverrides = import ./overrides.nix;

      packages = [
        pkgs.treefmt
        pkgs.nixfmt
        pkgs.ruff
        pkgs.cairo
      ];
    };
in
{
  profiles.shell.module = {
    imports = [ shell ];
  };
}
