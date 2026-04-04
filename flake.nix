{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }@inputs:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
        pyprojectName = "brick-mcp";
        python = pkgs.python314;
        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {
            inherit python;
          }).overrideScope
            (
              pkgs.lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                (workspace.mkPyprojectOverlay { sourcePreference = "wheel"; })
                (import ./overrides.nix)
                (final: prev: {
                  # Ensure all Python packages in the dependency graph see the same
                  # Python interpreter and standard library.  This is important for
                  # binary packages that link against Python (e.g. cairocffi).
                  "${pyprojectName}"= prev."${pyprojectName}".overrideAttrs (old: {
                    propagatedBuildInputs = [ ldview ] ++ (old.propagatedBuildInputs or []);
                  });
                })
              ]
            );
        inherit (pkgs.callPackages inputs.pyproject-nix.build.util { }) mkApplication;
        ldview = pkgs.callPackage ./pkgs/ldview.nix { };
        basePackage = mkApplication {
          venv = pythonSet.mkVirtualEnv "${pyprojectName}-env" workspace.deps.default;
          package = pythonSet.${pyprojectName};
        };
        # Wrap the MCP binary so ldview is on PATH at runtime.
        package = pkgs.symlinkJoin {
          name = pyprojectName;
          paths = [
            basePackage
            ldview
          ];
        };
      in
      {
        apps.default = {
          type = "app";
          program = "${package}/bin/${pyprojectName}";
        };

        packages = {
          default = package;
          inherit ldview;
        };

        formatter = pkgs.nixfmt;
      }
    );
}
