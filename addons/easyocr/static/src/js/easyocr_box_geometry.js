// Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
// License LGPL-3 (see LICENSE file).

/**
 * Where a box is once it has been dragged, or pulled by one of its corners.
 *
 * Nothing here touches the screen: it is arithmetic over a rectangle, kept
 * apart so it can be tested on its own with plain node. Coordinates are the
 * ones the module stores, in PDF points, with the origin at the top left of
 * the page, which is where the painting counts from too.
 */

/** How the four corners are named in a gesture. */
export const CORNERS = ['nw', 'ne', 'sw', 'se'];

/** The corner that stays put while another one is pulled. */
export const OPPOSITE = {nw: 'se', ne: 'sw', sw: 'ne', se: 'nw'};

/** Where a corner of a box is, in page points. */
export function cornerOf(box, corner) {
    return {
        x: corner === 'ne' || corner === 'se' ? box.x + box.width : box.x,
        y: corner === 'sw' || corner === 'se' ? box.y + box.height : box.y,
    };
}

/**
 * The corner a pull on `corner` has to leave alone.
 *
 * Taken once, when the drag starts, and not read back from the box on every
 * move: the box has already changed by then, and a corner read from it drifts
 * a little with every mouse move.
 */
export function anchorOf(box, corner) {
    return cornerOf(box, OPPOSITE[corner]);
}

/** The corner a point is holding, if it is holding one. */
export function handleAt(boxes, point, tolerance) {
    // From the last one drawn: it is the one on top, and the one being aimed at
    // when two boxes overlap.
    for (let index = boxes.length - 1; index >= 0; index--) {
        const box = boxes[index];
        for (const corner of CORNERS) {
            const at = cornerOf(box, corner);
            const near = Math.abs(point.x - at.x) <= tolerance
                && Math.abs(point.y - at.y) <= tolerance;
            if (near) {
                return {uid: box.uid, corner};
            }
        }
    }
    return null;
}

/** The box a point falls inside, the topmost one when they overlap. */
export function boxAt(boxes, point) {
    for (let index = boxes.length - 1; index >= 0; index--) {
        const box = boxes[index];
        const inside = point.x >= box.x && point.x <= box.x + box.width
            && point.y >= box.y && point.y <= box.y + box.height;
        if (inside) {
            return box;
        }
    }
    return null;
}

/** The rectangle between two points, whichever way the drag went. */
export function rectangleBetween(from, to) {
    return {
        x: Math.min(from.x, to.x),
        y: Math.min(from.y, to.y),
        width: Math.abs(to.x - from.x),
        height: Math.abs(to.y - from.y),
    };
}

/** Where a box lands when it is dragged: the point grabbed stays under the mouse. */
export function movedTo(box, point, offset, bounds) {
    return clamped({...box, x: point.x - offset.x, y: point.y - offset.y}, bounds);
}

/**
 * Where a box lands when one of its corners is pulled.
 *
 * The opposite corner is passed in, and not read from the box, because it is
 * the one thing about this that must not move. A pull past that corner turns
 * the box over rather than making it negative: a negative width is not a
 * smaller box, it is one that paints nothing and reads nothing.
 */
export function resizedTo(anchor, point, bounds) {
    return clamped(rectangleBetween(anchor, point), bounds);
}

/**
 * A box kept inside the page.
 *
 * Everything a box can do depends on the page under it: a box dragged off it
 * reads nothing and cannot be grabbed back, since there is nothing there to
 * grab. The original lets a box leave the page; this does not.
 */
export function clamped(box, bounds) {
    if (!bounds) {
        return box;
    }
    const width = Math.min(box.width, bounds.width);
    const height = Math.min(box.height, bounds.height);
    return {
        x: Math.min(Math.max(0, box.x), bounds.width - width),
        y: Math.min(Math.max(0, box.y), bounds.height - height),
        width,
        height,
    };
}
