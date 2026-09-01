const globals = require("@jest/globals");

const originalGlobals = new Map();

const vi = {
  fn: (...arguments_) => globals.jest.fn(...arguments_),
  spyOn: (...arguments_) => globals.jest.spyOn(...arguments_),
  stubGlobal(name, value) {
    if (!originalGlobals.has(name)) {
      originalGlobals.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    }
    Object.defineProperty(globalThis, name, {
      configurable: true,
      writable: true,
      value,
    });
  },
  unstubAllGlobals() {
    for (const [name, descriptor] of originalGlobals) {
      if (descriptor === undefined) delete globalThis[name];
      else Object.defineProperty(globalThis, name, descriptor);
    }
    originalGlobals.clear();
    globals.jest.restoreAllMocks();
  },
};

module.exports = { ...globals, vi };
