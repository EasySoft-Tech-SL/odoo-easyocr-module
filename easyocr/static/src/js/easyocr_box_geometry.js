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

/** Whether two rectangles share any area. */
export function overlaps(a, b) {
    return a.x < b.x + b.width && b.x < a.x + a.width
        && a.y < b.y + b.height && b.y < a.y + a.height;
}

/**
 * Where a box's name tag goes, so it covers no other box and no other tag.
 *
 * The tag sits above the box's top left corner, the way the module this is a
 * port of paints it. On a page where fields are a line apart, that spot is the
 * box above, and the tag hid it. So the spots are tried in turn -- above, below,
 * the same on the right, then beside the box on either side -- and the first one
 * clear of everything and inside the page wins. With none clear, the one that
 * hides least; never the box's own text.
 */
export function labelPlacement(box, tag, obstacles, bounds) {
    const candidates = [
        {x: box.x, y: box.y - tag.height},
        {x: box.x, y: box.y + box.height},
        {x: box.x + box.width - tag.width, y: box.y - tag.height},
        {x: box.x + box.width - tag.width, y: box.y + box.height},
        {x: box.x + box.width, y: box.y},
        {x: box.x - tag.width, y: box.y},
    ].map((spot) => ({...spot, width: tag.width, height: tag.height}));
    const fits = (rect) => !bounds || (
        rect.x >= 0 && rect.y >= 0
        && rect.x + rect.width <= bounds.width && rect.y + rect.height <= bounds.height
    );
    const covered = (rect) => obstacles.reduce((sum, other) => {
        const w = Math.min(rect.x + rect.width, other.x + other.width) - Math.max(rect.x, other.x);
        const h = Math.min(rect.y + rect.height, other.y + other.height) - Math.max(rect.y, other.y);
        return sum + (w > 0 && h > 0 ? w * h : 0);
    }, 0);
    const inside = candidates.filter(fits);
    const clear = inside.find((rect) => covered(rect) === 0);
    if (clear) {
        return clear;
    }
    // Everything around is taken: the spot that hides the least of the others,
    // and never the box's own text.
    const pool = inside.length ? inside : candidates;
    return pool.reduce((best, rect) => (covered(rect) < covered(best) ? rect : best));
}

/**
 * The text a box holds, from the page's text items, in reading order.
 *
 * A line counts when most of its height is inside the box, not when it merely
 * touches it: fields printed a line apart used to read the line under them as
 * well ("01/07/2026 02/07/2026"). Within a line, a character counts when its
 * middle is inside, so a box can take part of a line without a stray letter
 * from the edge.
 */
export function textInBox(items, box) {
    const left = Math.min(box.x, box.x + box.width);
    const right = Math.max(box.x, box.x + box.width);
    const top = Math.min(box.y, box.y + box.height);
    const bottom = Math.max(box.y, box.y + box.height);
    const hits = [];
    for (const item of items) {
        const height = Math.max(item.bottom - item.top, 0.01);
        const overlapY = Math.min(bottom, item.bottom) - Math.max(top, item.top);
        if (overlapY < height / 2 || item.right <= left || item.left >= right) {
            continue;
        }
        let piece = "";
        for (let index = 0; index < item.text.length; index++) {
            const middle = item.left + (index + 0.5) * item.charWidth;
            if (middle > left && middle < right) {
                piece += item.text[index];
            }
        }
        piece = piece.trim();
        if (piece) {
            hits.push({text: piece, top: item.top, left: item.left});
        }
    }
    hits.sort((a, b) => (Math.abs(a.top - b.top) > 5 ? a.top - b.top : a.left - b.left));
    return hits.map((hit) => hit.text).join(" ");
}
