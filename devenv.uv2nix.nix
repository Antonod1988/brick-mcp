{
  pkgs,
  config,
  lib,
  inputs,
  ...
}:
let
  cfg = config.languages.python;
  inherit (lib) types mkOption;
  python = cfg.interpreter;
  workspace = inputs.uv2nix.lib.workspace.loadWorkspace {
    workspaceRoot = config.languages.python.workspaceRoot;
  };
  overlay = workspace.mkPyprojectOverlay {
    sourcePreference = "wheel";
  };
  pythonSet =
    (pkgs.callPackage inputs.pyproject-nix.build.packages {
      inherit python;
    }).overrideScope
      (
        pkgs.lib.composeManyExtensions [
          inputs.pyproject-build-systems.overlays.default
          overlay
          cfg.pyprojectOverrides
          (
            _final: prev:
            builtins.mapAttrs (
              _name: pkg:
              if
                (pkg ? overrideAttrs)
                && (pkg ? src)
                && ((pkg.src.outputHash or null) != null)
                && (config.env ? NETRC)
                && (builtins.pathExists config.env.NETRC)
              then
                pkg.overrideAttrs (old: {
                  src = old.src.overrideAttrs (_: {
                    # Force curl to use our netrc + TLS verification
                    curlOpts = "--netrc-file ${config.env.NETRC}";
                    SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
                  });
                })
              else
                pkg

            ) prev
          )
        ]
      );
  editableOverlay = workspace.mkEditablePyprojectOverlay {
    root = "$REPO_ROOT";
  };
  editablePythonSet = pythonSet.overrideScope editableOverlay;
in
{
  options.languages.python = {
    interpreter = mkOption {
      default = pkgs.python3;
      type = types.package;
    };
    workspaceRoot = mkOption {
      default = ./.;
      type = types.path;
    };
    pyprojectOverrides = mkOption {
      default = final: prev: {
      };
    };
  };
  config = {
    languages.python = {
      uv.package = inputs.uv2nix.packages.${pkgs.system}.uv-bin;
    };
    packages = [
      cfg.uv.package
      config.outputs.python.virtualenv
    ];
    # Ensure uv to use Python from nixpkgs
    enterShell = ''
      unset PYTHONPATH
      export UV_LINK_MODE=copy
      export UV_NO_SYNC=1
      export UV_PYTHON_DOWNLOADS=never
      export UV_PYTHON_PREFERENCE=system
      export REPO_ROOT=$(git rev-parse --show-toplevel)
    '';
    outputs.python =
      let
        pyprojectName =
          (builtins.fromTOML (builtins.readFile (cfg.workspaceRoot + "/pyproject.toml"))).project.name;
        inherit (pkgs.callPackages inputs.pyproject-nix.build.util { }) mkApplication;
      in
      {
        virtualenv = editablePythonSet.mkVirtualEnv "${pyprojectName}-dev-env" workspace.deps.all;
        app = mkApplication {
          venv = pythonSet.mkVirtualEnv "${pyprojectName}-env" workspace.deps.default;
          package = pythonSet.${pyprojectName};
        };

      };
  };
}
