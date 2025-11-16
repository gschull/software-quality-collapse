const { add } = require('./add');

describe('add', () => {
  it('adds positive numbers', () => {
    expect(add(2, 3)).toBe(5);
  });

  it('adds negative numbers', () => {
    expect(add(-2, -3)).toBe(-5);
  });
});
