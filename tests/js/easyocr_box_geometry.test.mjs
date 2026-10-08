// Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
// License LGPL-3 (see LICENSE file).

/**
 * The arithmetic behind dragging and pulling a box, on its own.
 *
 * A drag is a sequence of mouse moves over the same box, so most of what can go
 * wrong only shows up on the second move: a box whose anchor is read back from
 * itself drifts a little with every one of them, and a pull past the opposite
 * corner used to be the way a box became negative and stopped painting. Both
 * are only visible in a run of moves, which is what these do.
 *
 * Run with: node --test
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
    anchorOf, boxAt, clamped, cornerOf, handleAt, movedTo, rectangleBetween, resizedTo,
} from '../../addons/easyocr/static/src/js/easyocr_box_geometry.js';

// A page the size of a sheet of A4 in PDF points, which is what the viewer
// carries for every page it paints.
const PAGE = {width: 595, height: 842};

const box = (over = {}) => ({uid: 1, x: 100, y: 200, width: 80, height: 20, ...over});

/** A drag, as the browser delivers it: a point per mouse move, in order. */
const drag = (start, path, apply) => {
    let current = start;
    for (const point of path) {
        current = {...current, ...apply(current, point)};
    }
    return current;
};

test('a corner is where the box says it is', () => {
    const one = box();
    assert.deepEqual(cornerOf(one, 'nw'), {x: 100, y: 200});
    assert.deepEqual(cornerOf(one, 'ne'), {x: 180, y: 200});
    assert.deepEqual(cornerOf(one, 'sw'), {x: 100, y: 220});
    assert.deepEqual(cornerOf(one, 'se'), {x: 180, y: 220});
});

test('the anchor of a pull is the corner opposite the one being pulled', () => {
    const one = box();
    assert.deepEqual(anchorOf(one, 'nw'), cornerOf(one, 'se'));
    assert.deepEqual(anchorOf(one, 'se'), cornerOf(one, 'nw'));
    assert.deepEqual(anchorOf(one, 'ne'), cornerOf(one, 'sw'));
    assert.deepEqual(anchorOf(one, 'sw'), cornerOf(one, 'ne'));
});

test('the anchor does not move over a whole drag', () => {
    // The bug this guards: reading the anchor from the box on every move makes
    // it creep, and the box grows a sliver with each one.
    const one = box();
    const anchor = anchorOf(one, 'nw');
    const path = [{x: 90, y: 190}, {x: 80, y: 180}, {x: 70, y: 170}];
    const end = drag(one, path, (current, point) => resizedTo(anchor, point, PAGE));
    assert.deepEqual(anchor, {x: 180, y: 220});
    assert.deepEqual(
        {x: end.x, y: end.y, width: end.width, height: end.height},
        {x: 70, y: 170, width: 110, height: 50},
    );
});

test('pulling a corner past its opposite turns the box over', () => {
    const one = box();
    // Dragging the north-west corner to the far side of the south-east one.
    const anchor = anchorOf(one, 'nw');
    const end = resizedTo(anchor, {x: 220, y: 260}, PAGE);
    assert.deepEqual(end, {x: 180, y: 220, width: 40, height: 40});
});

test('a box that is turned over is still a box', () => {
    // Negative width and height are what paint nothing: the rectangle has to
    // come back with a size, whatever direction the mouse went.
    const rectangle = rectangleBetween({x: 300, y: 300}, {x: 100, y: 100});
    assert.deepEqual(rectangle, {x: 100, y: 100, width: 200, height: 200});
});

test('dragging moves the box by the same amount as the mouse', () => {
    const one = box();
    const offset = {x: 10, y: 5};
    const end = movedTo(one, {x: 210, y: 305}, offset, PAGE);
    assert.deepEqual({x: end.x, y: end.y}, {x: 200, y: 300});
    assert.equal(end.width, 80);
    assert.equal(end.height, 20);
});

test('the point grabbed stays under the mouse over a whole drag', () => {
    const one = box();
    const grabbed = {x: 120, y: 210};
    const offset = {x: grabbed.x - one.x, y: grabbed.y - one.y};
    const path = [{x: 130, y: 220}, {x: 200, y: 400}, {x: 300, y: 500}];
    const end = drag(one, path, (current, point) => movedTo(current, point, offset, PAGE));
    assert.equal(end.x + offset.x, 300);
    assert.equal(end.y + offset.y, 500);
});

test('a box cannot be dragged off the page', () => {
    // Off the page there is nothing to read and nothing to grab it back by.
    const one = box();
    const end = movedTo(one, {x: -50, y: -60}, {x: 0, y: 0}, PAGE);
    assert.deepEqual({x: end.x, y: end.y}, {x: 0, y: 0});
});

test('a box cannot be dragged out of the far corner either', () => {
    const one = box();
    const end = movedTo(one, {x: 5000, y: 5000}, {x: 0, y: 0}, PAGE);
    assert.equal(end.x, PAGE.width - one.width);
    assert.equal(end.y, PAGE.height - one.height);
});

test('a box bigger than the page is cut down to it', () => {
    const huge = box({x: 0, y: 0, width: 900, height: 900});
    assert.deepEqual(clamped(huge, PAGE), {x: 0, y: 0, width: 595, height: 842});
});

test('without page bounds nothing is clamped', () => {
    // The viewer hands the page it is painting when it knows it, and nothing
    // otherwise; arithmetic that only works with bounds is arithmetic that
    // breaks the day they are missing.
    const one = box({x: -10, y: -10});
    assert.deepEqual(clamped(one, null), one);
});

test('a point on a corner holds it', () => {
    const boxes = [box()];
    assert.deepEqual(handleAt(boxes, {x: 180, y: 220}, 7), {uid: 1, corner: 'se'});
    assert.deepEqual(handleAt(boxes, {x: 176, y: 224}, 7), {uid: 1, corner: 'se'});
});

test('a point away from every corner holds nothing', () => {
    const boxes = [box()];
    assert.equal(handleAt(boxes, {x: 140, y: 210}, 7), null);
    assert.equal(handleAt(boxes, {x: 190, y: 220}, 7), null);
});

test('the corner of the box on top is the one that is held', () => {
    // Two boxes sharing a corner: the last one drawn is the one being aimed at.
    const under = box({uid: 1});
    const over = box({uid: 2, x: 100, y: 200});
    assert.deepEqual(handleAt([under, over], {x: 100, y: 200}, 7), {uid: 2, corner: 'nw'});
});

test('a point inside a box is on it, edges included', () => {
    const boxes = [box()];
    assert.equal(boxAt(boxes, {x: 140, y: 210}).uid, 1);
    assert.equal(boxAt(boxes, {x: 100, y: 200}).uid, 1);
    assert.equal(boxAt(boxes, {x: 180, y: 220}).uid, 1);
    assert.equal(boxAt(boxes, {x: 181, y: 210}), null);
});

test('the box on top is the one picked up', () => {
    const under = box({uid: 1});
    const over = box({uid: 2, x: 120, y: 200});
    assert.equal(boxAt([under, over], {x: 140, y: 210}).uid, 2);
});
