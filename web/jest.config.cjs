module.exports = {
  rootDir: __dirname,
  testEnvironment: "jsdom",
  roots: ["<rootDir>/src"],
  testMatch: ["**/*.test.ts", "**/*.test.tsx"],
  setupFilesAfterEnv: [
    "<rootDir>/src/test/web-globals.cjs",
    "<rootDir>/src/test/setup.ts",
  ],
  moduleNameMapper: {
    "^vitest$": "<rootDir>/src/test/vitest-shim.cjs",
  },
  transform: {
    "^.+\\.[jt]sx?$": [
      "babel-jest",
      {
        presets: [
          [require.resolve("@babel/preset-env"), { targets: { node: "current" }, modules: "commonjs" }],
          [require.resolve("@babel/preset-react"), { runtime: "automatic" }],
          require.resolve("@babel/preset-typescript"),
        ],
      },
    ],
  },
};
