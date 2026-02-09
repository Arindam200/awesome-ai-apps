import React, { useEffect, useRef } from 'react'
import * as PIXI from 'pixi.js'

export default function PixiTable({ snapshot, eventLog }) {
  const ref = useRef(null)
  const appRef = useRef(null)
  const stateRef = useRef({ potText: null, streetText: null, communityText: null, cardsLayer: null })
  const prevPotRef = useRef(0)
  const prevCommunityRef = useRef([])
  const prevBalancesRef = useRef({ seat0: null, seat1: null })

  useEffect(() => {
    const app = new PIXI.Application()
    appRef.current = app
    let cancelled = false

    const init = async () => {
      await app.init({
        resizeTo: ref.current,
        background: '#0b0f1a',
        antialias: true
      })
      if (cancelled) return
      ref.current.appendChild(app.canvas)

      const table = new PIXI.Graphics()
      table.beginFill(0x0f1629)
      table.drawRoundedRect(30, 30, 520, 260, 24)
      table.endFill()
      table.lineStyle(2, 0x243b6b)
      table.drawRoundedRect(30, 30, 520, 260, 24)
      app.stage.addChild(table)

      const potText = new PIXI.Text('Pot: 0', { fill: 0xe6f1ff, fontSize: 14 })
      potText.position.set(50, 50)
      app.stage.addChild(potText)

      const streetText = new PIXI.Text('Street: -', { fill: 0x9fb3c8, fontSize: 12 })
      streetText.position.set(50, 70)
      app.stage.addChild(streetText)

      const communityText = new PIXI.Text('Community: -', { fill: 0x9fb3c8, fontSize: 12 })
      communityText.position.set(50, 90)
      app.stage.addChild(communityText)

      const cardsLayer = new PIXI.Container()
      cardsLayer.position.set(80, 140)
      app.stage.addChild(cardsLayer)

      stateRef.current = { potText, streetText, communityText, cardsLayer }
    }
    init()

    return () => {
      cancelled = true
      app.destroy(true, { children: true })
    }
  }, [])

  useEffect(() => {
    const app = appRef.current
    if (!app || !snapshot) return
    const { potText, streetText, communityText, cardsLayer } = stateRef.current
    if (!potText || !streetText || !communityText || !cardsLayer) return

    potText.text = `Pot: ${snapshot.pot ?? 0}`
    streetText.text = `Street: ${snapshot.street || '-'}`
    communityText.text = `Community: ${(snapshot.community_cards || []).join(' ') || '-'}`

    const prevPot = prevPotRef.current
    const next = snapshot.pot ?? 0
    if (next > prevPot) {
      const chip = new PIXI.Graphics()
      chip.beginFill(0xffc857)
      chip.drawCircle(0, 0, 6)
      chip.endFill()
      chip.x = 120
      chip.y = 230
      app.stage.addChild(chip)
      let t = 0
      app.ticker.add((delta) => {
        t += delta * 0.03
        chip.x = 120 + t * 200
        chip.y = 230 - t * 120
        if (t > 1) {
          app.stage.removeChild(chip)
          chip.destroy()
        }
      })
    }
    prevPotRef.current = next

    const prevCommunity = prevCommunityRef.current
    const currCommunity = snapshot.community_cards || []
    if (currCommunity.length > prevCommunity.length) {
      for (let i = prevCommunity.length; i < currCommunity.length; i++) {
        const card = drawCard(currCommunity[i])
        card.x = -40
        card.y = 60
        cardsLayer.addChild(card)
        animateCardTo(card, i * 60, 0, app)
      }
    }
    if (currCommunity.length < prevCommunity.length) {
      cardsLayer.removeChildren()
    }
    prevCommunityRef.current = currCommunity

    const seat0 = snapshot.my_balance ?? 0
    const seat1 = snapshot.opponents?.[0]?.stack ?? 0
    const prevBalances = prevBalancesRef.current
    if (prevBalances.seat0 !== null && seat0 < prevBalances.seat0) {
      spawnParticles(app, 140, 230, 0xff6b6b)
    }
    if (prevBalances.seat1 !== null && seat1 < prevBalances.seat1) {
      spawnParticles(app, 420, 120, 0xff6b6b)
    }
    prevBalancesRef.current = { seat0, seat1 }
  }, [snapshot])

  useEffect(() => {
    const app = appRef.current
    if (!app || !eventLog) return
    if (!eventLog.amount || eventLog.amount <= 0) return
    const seat = eventLog.player_seat
    if (seat === 0) {
      spawnChipMove(app, 140, 230, 300, 160)
    } else if (seat === 1) {
      spawnChipMove(app, 420, 120, 300, 160)
    }
  }, [eventLog])

  return <div ref={ref} className="pixi-canvas" />
}

function drawCard(label) {
  const container = new PIXI.Container()
  const bg = new PIXI.Graphics()
  bg.beginFill(0x101828)
  bg.lineStyle(2, 0x3b4f7a)
  bg.drawRoundedRect(0, 0, 48, 64, 6)
  bg.endFill()
  const text = new PIXI.Text(label, { fill: 0xe6f1ff, fontSize: 14 })
  text.position.set(8, 6)
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

function spawnParticles(app, x, y, color) {
  for (let i = 0; i < 10; i++) {
    const p = new PIXI.Graphics()
    p.beginFill(color)
    p.drawCircle(0, 0, 2)
    p.endFill()
    p.x = x
    p.y = y
    const vx = (Math.random() - 0.5) * 2
    const vy = (Math.random() - 0.5) * 2
    let life = 30 + Math.random() * 20
    app.stage.addChild(p)
    app.ticker.add((delta) => {
      life -= delta
      p.x += vx * delta
      p.y += vy * delta
      p.alpha = Math.max(0, life / 40)
      if (life <= 0) {
        app.stage.removeChild(p)
        p.destroy()
      }
    })
  }
}
