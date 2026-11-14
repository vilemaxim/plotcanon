---
id: blood-on-the-salt-stair
type: mod
title: "Blood on the Salt Stair"
aliases: ["Blood on the Salt Stair", "the stair mod"]
mod_writer: dev
state: approved
campaign: tideward
events: [e03-storm-moon]
slot: 1
duration_est: 90
canon: approved
visibility: gm-only
features:
  npcs: [ysolde-marr, harrow-dunmore]
  factions: [harbour-wardens]
  locations: [the-salt-stair]
  plots: [the-salt-tax-revolt]
requires:
  - {entity: harrow-dunmore, field: status, in: [alive, departed]}
  - {entity: ysolde-marr, field: status, equals: alive}
expected_changes:
  harrow-dunmore: "is hurt, shamed or driven off the stair"
  the-salt-stair: "is held by one side at dawn"
supersedes: []
---

## Premise

The picket moves down the stair at midnight. The smuggler is on it, and so is the captain.

## Hooks

- Wardens are ordered down the stair.
- Pan-workers are told to hold the third landing.
- The smuggler has hired a guard.

## Scene Breakdown

### 1. The top landing

**Find:** the captain giving an order she does not like. **If players do nothing:** the picket descends.

### 2. The third landing

**Find:** the smuggler between the two lines. **If players do nothing:** someone pushes.

### 3. The edge

**Find:** one person too close to it. **If players do nothing:** they fall.

## NPC Casting

The captain needs stillness. The smuggler must be able to lose a fight.

## Player Agency Notes

Players can fail, there is more than one way in, and the ending turns on what they choose.

## Possible Outcomes

Nobody falls, the smuggler falls, or a player does.

## Rewards

The stair, for whichever side holds it at dawn.

## Logistics

Stair set, twenty players, 60 minutes. Safety brief required for scene 3.

## GM Notes

This is the mod most likely to kill the smuggler. Two others need him.
