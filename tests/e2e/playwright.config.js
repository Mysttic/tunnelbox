const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: ".",
  timeout: 20000,
  fullyParallel: false,
  use: { baseURL: "http://localhost:8099" },
  webServer: {
    command: "node serve.js",
    url: "http://localhost:8099/",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
