import { describe, expect, it } from 'vitest';

import { calculateContainRenderArea, convertToDeviceCoords } from './utils';

describe('远程桌面坐标换算', () => {
  it('会排除 contain 产生的上下留白', () => {
    const result = calculateContainRenderArea(1000, 1000, 1920, 1080, 500, 100);

    expect(result.renderedWidth).toBeCloseTo(1000);
    expect(result.renderedHeight).toBeCloseTo(562.5);
    expect(result.offsetY).toBeCloseTo(218.75);
    expect(result.isValidClick).toBe(false);
  });

  it('会把实际渲染区域边缘映射到设备边缘坐标', () => {
    const result = calculateContainRenderArea(1000, 1000, 1920, 1080, 999, 781.25);
    const coords = convertToDeviceCoords(
      result.adjustedX,
      result.adjustedY,
      result.renderedWidth,
      result.renderedHeight,
      1920,
      1080,
    );

    expect(result.isValidClick).toBe(true);
    expect(coords).toEqual({ x: 1918, y: 1079 });
  });
});
