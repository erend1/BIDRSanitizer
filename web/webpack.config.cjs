const fs = require("node:fs");
const path = require("node:path");

const HtmlWebpackPlugin = require("html-webpack-plugin");

class RuntimeConfigPlugin {
  apply(compiler) {
    compiler.hooks.thisCompilation.tap("RuntimeConfigPlugin", (compilation) => {
      compilation.hooks.processAssets.tap(
        {
          name: "RuntimeConfigPlugin",
          stage: compiler.webpack.Compilation.PROCESS_ASSETS_STAGE_ADDITIONAL,
        },
        () => {
          const sourcePath = path.join(__dirname, "public", "runtime-config.js");
          compilation.emitAsset(
            "runtime-config.js",
            new compiler.webpack.sources.RawSource(fs.readFileSync(sourcePath)),
          );
        },
      );
    });
  }
}

module.exports = (_environment, arguments_) => {
  const production = arguments_.mode === "production";

  return {
    context: __dirname,
    target: "web",
    mode: production ? "production" : "development",
    entry: "./src/main.tsx",
    output: {
      path: path.join(__dirname, "dist"),
      filename: production
        ? "assets/[name].[contenthash:8].js"
        : "assets/[name].js",
      publicPath: "/",
      clean: true,
    },
    devtool: production ? "source-map" : "cheap-module-source-map",
    resolve: {
      extensions: [".tsx", ".ts", ".jsx", ".js"],
    },
    module: {
      rules: [
        {
          test: /\.tsx?$/,
          exclude: /node_modules/,
          use: {
            loader: "babel-loader",
            options: {
              presets: [
                [require.resolve("@babel/preset-env"), { targets: "defaults", modules: false }],
                [require.resolve("@babel/preset-react"), { runtime: "automatic" }],
                require.resolve("@babel/preset-typescript"),
              ],
            },
          },
        },
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"],
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({
        template: path.join(__dirname, "index.html"),
        scriptLoading: "defer",
      }),
      new RuntimeConfigPlugin(),
    ],
    devServer: {
      host: "127.0.0.1",
      port: 4173,
      allowedHosts: ["127.0.0.1", "localhost"],
      historyApiFallback: false,
      hot: true,
      liveReload: true,
      proxy: [
        {
          context: ["/api"],
          target: process.env.BIDR_DEV_API_TARGET ?? "http://127.0.0.1:8765",
          changeOrigin: true,
        },
      ],
      client: {
        overlay: true,
      },
    },
    performance: {
      hints: false,
    },
  };
};
