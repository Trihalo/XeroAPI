const daisyui = require("daisyui");

module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  plugins: [daisyui],
  daisyui: {
    themes: [
      {
        light: {
          ...require("daisyui/src/colors/themes")["[data-theme=light]"],
          primary: "#003464",
          secondary: "#ED5C5B",
          accent: "#FFEBEB",
        },
      },
    ],
    darkTheme: false,
  },
};
