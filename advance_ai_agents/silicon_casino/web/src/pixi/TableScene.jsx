import React, { useEffect, useRef } from 'react'
import * as PIXI from 'pixi.js'

export default function TableScene({ snapshot, eventLog, showdown, mode = 'full', hideHud = false }) {
  const ref = useRef(null)
  const appRef = useRef(null)
  const stateRef = useRef({
    potText: null,
    streetText: null,
    communityText: null,
    cardsLayer: null,
    seat0: null,
    seat1: null,
    seat0Text: null,
    seat1Text: null,
    seat0Stack: null,
    seat1Stack: null,
    thought0: null,
    thought1: null,
    fxLayer: null
  })
  const prevPotRef = useRef(0)
  const prevCommunityRef = useRef([])

  useEffect(() => {
    const app = new PIXI.Application()
    appRef.current = app
    let cancelled = false

    const init = async () => {
      await app.init({
        resizeTo: ref.current,
        background: '#0a0f1c',
        antialias: true
      })
      if (cancelled) return
      ref.current.appendChild(app.canvas)

      const table = new PIXI.Graphics()
      const w = mode === 'preview' ? 420 : 640
      const h = mode === 'preview' ? 220 : 320
      if (mode !== 'preview' && !hideHud) {
        table.beginFill(0x0f1629)
        table.drawRoundedRect(20, 20, w, h, 28)
        table.endFill()
      }
      table.lineStyle(2, 0x2c3a66, mode === 'preview' ? 0.4 : 1)
      table.drawRoundedRect(20, 20, w, h, 28)
      if (mode === 'preview') {
        table.lineStyle(1, 0x3b4f7a, 0.3)
        table.moveTo(40, 130)
        table.lineTo(w - 40, 130)
      }
      app.stage.addChild(table)

      const potText = new PIXI.Text('Pot: 0', { fill: 0xe6f1ff, fontSize: mode === 'preview' ? 12 : 14 })
      potText.position.set(40, 36)
      potText.alpha = hideHud ? 0 : 1
      app.stage.addChild(potText)

      const streetText = new PIXI.Text('Street: -', { fill: 0x9fb3c8, fontSize: mode === 'preview' ? 10 : 12 })
      streetText.position.set(40, 56)
      streetText.alpha = hideHud ? 0 : 1
      app.stage.addChild(streetText)

      const communityText = new PIXI.Text('Community: -', { fill: 0x9fb3c8, fontSize: mode === 'preview' ? 10 : 12 })
      communityText.position.set(40, 76)
      communityText.alpha = hideHud ? 0 : 1
      app.stage.addChild(communityText)

      const cardsLayer = new PIXI.Container()
      cardsLayer.position.set(mode === 'preview' ? 70 : 90, mode === 'preview' ? 110 : 150)
      cardsLayer.alpha = hideHud ? 0 : 1
      app.stage.addChild(cardsLayer)

      const fxLayer = new PIXI.Container()
      app.stage.addChild(fxLayer)

      const seat0 = drawSeat(mode)
      seat0.position.set(mode === 'preview' ? 60 : 90, mode === 'preview' ? 200 : 300)
      seat0.alpha = hideHud ? 0 : 1
      app.stage.addChild(seat0)

      const seat1 = drawSeat(mode)
      seat1.position.set(mode === 'preview' ? 280 : 430, mode === 'preview' ? 70 : 80)
      seat1.alpha = hideHud ? 0 : 1
      app.stage.addChild(seat1)

      const seat0Text = new PIXI.Text('You', { fill: 0xaef2ff, fontSize: mode === 'preview' ? 9 : 12 })
      seat0Text.position.set(seat0.x + 10, seat0.y + 8)
      seat0Text.alpha = hideHud ? 0 : 1
      app.stage.addChild(seat0Text)

      const seat0Stack = new PIXI.Text('Stack: -', { fill: 0xcbd5f5, fontSize: mode === 'preview' ? 9 : 12 })
      seat0Stack.position.set(seat0.x + 10, seat0.y + 26)
      seat0Stack.alpha = hideHud ? 0 : 1
      app.stage.addChild(seat0Stack)

      const seat1Text = new PIXI.Text('Opponent', { fill: 0xff9de6, fontSize: mode === 'preview' ? 9 : 12 })
      seat1Text.position.set(seat1.x + 10, seat1.y + 8)
      seat1Text.alpha = hideHud ? 0 : 1
      app.stage.addChild(seat1Text)

      const seat1Stack = new PIXI.Text('Stack: -', { fill: 0xcbd5f5, fontSize: mode === 'preview' ? 9 : 12 })
      seat1Stack.position.set(seat1.x + 10, seat1.y + 26)
      seat1Stack.alpha = hideHud ? 0 : 1
      app.stage.addChild(seat1Stack)

      const thought0 = new PIXI.Text('', { fill: 0x7dd3fc, fontSize: mode === 'preview' ? 8 : 10 })
      thought0.position.set(seat0.x - 10, seat0.y - 18)
      thought0.alpha = hideHud ? 0 : 1
      app.stage.addChild(thought0)

      const thought1 = new PIXI.Text('', { fill: 0xf9a8d4, fontSize: mode === 'preview' ? 8 : 10 })
      thought1.position.set(seat1.x - 10, seat1.y - 18)
      thought1.alpha = hideHud ? 0 : 1
      app.stage.addChild(thought1)

      stateRef.current = {
        potText,
        streetText,
        communityText,
        cardsLayer,
        seat0,
        seat1,
        seat0Text,
        seat1Text,
        seat0Stack,
        seat1Stack,
        thought0,
        thought1,
        fxLayer
      }
    }

    init()

    return () => {
      cancelled = true
      app.destroy(true, { children: true })
    }
  }, [mode])

  useEffect(() => {
    const app = appRef.current
    if (!app || !snapshot) return
    const {
      potText,
      streetText,
      communityText,
      cardsLayer,
      seat0Text,
      seat1Text,
      seat0Stack,
      seat1Stack
    } = stateRef.current
    if (!potText || !streetText || !communityText || !cardsLayer) return

    potText.text = `Pot: ${snapshot.pot ?? 0}`
    streetText.text = `Street: ${snapshot.street || '-'}`
    communityText.text = `Community: ${(snapshot.community_cards || []).join(' ') || '-'}`

    seat0Text.text = 'You'
    seat0Stack.text = `Stack: ${snapshot.my_balance ?? '-'}`

    const opp = snapshot.opponents?.[0]
    seat1Text.text = opp?.name || 'Opponent'
    seat1Stack.text = `Stack: ${opp?.stack ?? '-'}`

    const prevPot = prevPotRef.current
    const next = snapshot.pot ?? 0
    if (next > prevPot) {
      spawnChip(app, stateRef.current.fxLayer, mode)
    }
    prevPotRef.current = next

    const prevCommunity = prevCommunityRef.current
    const currCommunity = snapshot.community_cards || []
    if (currCommunity.length > prevCommunity.length) {
      for (let i = prevCommunity.length; i < currCommunity.length; i++) {
        const card = drawCard(currCommunity[i], mode)
        card.x = -40
        card.y = 40
        cardsLayer.addChild(card)
        animateCardTo(card, i * (mode === 'preview' ? 46 : 60), 0, app)
      }
    }
    if (currCommunity.length < prevCommunity.length) {
      cardsLayer.removeChildren()
    }
    prevCommunityRef.current = currCommunity
  }, [snapshot, mode])

  useEffect(() => {
    const app = appRef.current
    if (!app || !eventLog || hideHud) return
    if (!eventLog.amount || eventLog.amount <= 0) return
    const seat = eventLog.player_seat
    if (seat === 0) {
      spawnChipMove(app, 140, mode === 'preview' ? 200 : 300, mode === 'preview' ? 240 : 320, 160)
    } else if (seat === 1) {
      spawnChipMove(app, mode === 'preview' ? 300 : 470, mode === 'preview' ? 90 : 110, mode === 'preview' ? 240 : 320, 160)
    }
    spawnBurn(app, stateRef.current.fxLayer, seat, mode)
    if (eventLog.thought_log) {
      showThoughtBubble(eventLog.player_seat, eventLog.thought_log, stateRef.current)
    }
  }, [eventLog, mode])

  useEffect(() => {
    if (!showdown?.length) return
    const app = appRef.current
    if (!app || hideHud) return
    const flash = new PIXI.Graphics()
    flash.beginFill(0x38bdf8, 0.2)
    flash.drawRect(0, 0, app.renderer.width, app.renderer.height)
    flash.endFill()
    app.stage.addChild(flash)
    setTimeout(() => {
      app.stage.removeChild(flash)
      flash.destroy()
    }, 600)
  }, [showdown])

  return <div ref={ref} className={`pixi-canvas ${mode}`} />
}

function drawSeat(mode) {
  const seat = new PIXI.Graphics()
  seat.beginFill(0x0b1220)
  seat.lineStyle(2, 0x2c3a66)
  seat.drawRoundedRect(0, 0, mode === 'preview' ? 120 : 160, mode === 'preview' ? 46 : 60, 8)
  seat.endFill()
  return seat
}

function drawCard(label, mode) {
  const container = new PIXI.Container()
  const bg = new PIXI.Graphics()
  bg.beginFill(0x101828)
  bg.lineStyle(2, 0x3b4f7a)
  bg.drawRoundedRect(0, 0, mode === 'preview' ? 36 : 48, mode === 'preview' ? 50 : 64, 6)
  bg.endFill()
  const text = new PIXI.Text(label, { fill: 0xe6f1ff, fontSize: mode === 'preview' ? 12 : 14 })
  text.position.set(6, 6)
  container.addChild(bg, text)
  return container
}

function animateCardTo(card, x, y, app) {
  let t = 0
  const startX = card.x
  const startY = card.y
  app.ticker.add((delta) => {
    t += delta * 0.05
    const eased = Math.min(t, 1)
    card.x = startX + (x - startX) * eased
    card.y = startY + (y - startY) * eased
  })
}

function spawnChip(app, layer, mode) {
  if (!layer) return
  const chip = new PIXI.Graphics()
  chip.beginFill(0xffc857)
  chip.drawCircle(0, 0, mode === 'preview' ? 4 : 6)
  chip.endFill()
  chip.x = mode === 'preview' ? 200 : 300
  chip.y = mode === 'preview' ? 160 : 200
  layer.addChild(chip)
  let t = 0
  app.ticker.add((delta) => {
    t += delta * 0.03
    chip.x = chip.x + t * 20
    chip.y = chip.y - t * 10
    if (t > 1) {
      layer.removeChild(chip)
      chip.destroy()
    }
  })
}

function spawnChipMove(app, sx, sy, tx, ty) {
  const chip = new PIXI.Graphics()
  chip.beginFill(0xffc857)
  chip.drawCircle(0, 0, 6)
  chip.endFill()
  chip.x = sx
  chip.y = sy
  app.stage.addChild(chip)
  let t = 0
  app.ticker.add((delta) => {
    t += delta * 0.04
    const eased = Math.min(t, 1)
    chip.x = sx + (tx - sx) * eased
    chip.y = sy + (ty - sy) * eased
    if (eased >= 1) {
      app.stage.removeChild(chip)
      chip.destroy()
    }
  })
}

function spawnBurn(app, layer, seat, mode) {
  if (!layer) return
  const origin =
    seat === 0
      ? { x: mode === 'preview' ? 150 : 180, y: mode === 'preview' ? 210 : 250 }
      : { x: mode === 'preview' ? 320 : 460, y: mode === 'preview' ? 100 : 130 }
  for (let i = 0; i < 16; i++) {
    const p = new PIXI.Graphics()
    p.beginFill(0xff5c8a, 0.8)
    p.drawCircle(0, 0, 2)
    p.endFill()
    p.x = origin.x
    p.y = origin.y
    const vx = (Math.random() - 0.5) * 2
    const vy = -Math.random() * 2 - 1
    let life = 40 + Math.random() * 30
    layer.addChild(p)
    app.ticker.add((delta) => {
      life -= delta
      p.x += vx * delta * 2
      p.y += vy * delta * 2
      p.alpha = Math.max(0, life / 60)
      if (life <= 0) {
        layer.removeChild(p)
        p.destroy()
      }
    })
  }
}

function showThoughtBubble(seat, text, state) {
  const target = seat === 0 ? state.thought0 : state.thought1
  if (!target) return
  target.text = `Thinking: ${text.slice(0, 80)}`
  target.alpha = 1
  setTimeout(() => {
    target.text = ''
  }, 6000)
}
