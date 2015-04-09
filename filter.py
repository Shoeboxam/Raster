import copy

from Raster.analyze import *
from Raster.raster import *
from Utility.modular_math import *


def colorize(raster, hue, sat=0., val=0., hue_opacity=1., sat_opacity=0, val_opacity=0):

    raster.to_hsv()

    # Modify each pixel
    for index, (h, s, v) in enumerate(raster.colors):

        # Blend in values at given opacity
        # TODO: Slide range to val instead of set range to val
        h = circular_mean([hue, h], [hue_opacity, 1 - hue_opacity])
        s = linear_mean([sat, s], [sat_opacity, 1 - sat_opacity])
        v = linear_mean([val, v], [val_opacity, 1 - val_opacity])

        raster.colors[index] = [h, s, v]

    return raster


def contrast(raster, value_multiplier):

    raster.to_hsv()

    avg_val = val_mean(raster)

    # period_hue = 1
    period_val = pi / min([avg_val, 1 - avg_val])

    min_val = min(raster.channel('V'))

    # Modify each pixel
    for index, (h, s, v) in enumerate(raster.colors):

        # Blend in values at given opacity
        v -= sin(period_val * (v - min_val)) * value_multiplier
        v = clamp(v, 0, 1)

        raster.colors[index] = [h, s, v]

    return raster


def brightness(raster, light_difference):
    raster.colors[:, 2] += light_difference
    minimum, maximum = lightness_extrema(raster)
    if minimum < 0:
        raster.colors[:, 2] -= minimum
    if maximum > 1:
        raster.colors[:, 2] -= (maximum - 1)

    raster.colors = np.clip(raster.colors, 0., 1.)
    return raster


def image_decompose(raster, layers):
    """Slice image by a given number of lightness zones"""

    minimum, maximum = lightness_extrema(raster)
    # print("Minimum: " + str(minimum))
    # print("Maximum: " + str(maximum))

    brightnesses = raster.channel('V')

    raster_components = []
    layer_range = (maximum - minimum) / layers
    period = pi / layer_range
    # print("Layer Range: " + str(layer_range))
    # print("Period: " + str(period))

    for layer in range(layers):
        new_image = copy.deepcopy(raster)

        # Starting offset + layer spacings + half spacing
        horizontal_translation = minimum + layer_range * layer + layer_range / 2

        for index, lightness in enumerate(brightnesses):
            # If lightness is within mask's first period...
            if horizontal_translation - layer_range <= lightness <= horizontal_translation + layer_range:
                # Resolve edge case to preserve transparency in low and high lightness
                if minimum + layer_range / 2 <= lightness <= maximum - layer_range * .5:
                    bright_mask = cos(period * (lightness - horizontal_translation)) * .5 + .5
                else:
                    bright_mask = 1
            else:
                bright_mask = 0
            new_image.mask[index] = clamp(new_image.mask[index] * bright_mask)
        # print("Horizontal Translation: " + str(horizontal_translation))
        # print(new_image.mask)
        raster_components.append(new_image)

    return raster_components


def image_composite(raster_list):
    """Combine all input layers with additive alpha blending"""

    width = raster_list[0].width
    height = raster_list[0].height

    pixel_layers = []
    for image in raster_list:
        pixel_layers.append(image.with_alpha())

    pixel_accumulator = []

    # Take transpose of pixel layers to produce a list of corresponding pixels
    for pixel_profile in np.array(zip(*pixel_layers)):

        # print(pixel_profile[:, 3])  # View alpha values of pixel profile

        # Opacity is the sum of alpha channels
        opacity = sum(pixel_profile[:, 3])

        # If one of the pixels has opacity
        if opacity != 0:
            pixel = []

            # Treat opacity as weight
            weights = pixel_profile[:, 3]
            # print(pixel_profile)

            # Condense profile down into one representative pixel
            pixel.append(circular_mean(pixel_profile[:, 0], weights))  # R
            pixel.append(linear_mean(pixel_profile[:, 1], weights))    # G
            pixel.append(linear_mean(pixel_profile[:, 2], weights))    # B
            pixel.append(clamp(opacity))                               # A
            pixel_accumulator.append(pixel)
            # print(pixel)
        else:
            pixel_accumulator.append([0, 0, 0, 0])

    return Raster(pixel_accumulator, width, height, raster_list[0].mode, channels=4, bits=8, alpha=True)