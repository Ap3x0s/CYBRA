/** Р’РµСЂС…РЅСЏСЏ РїРѕР»РѕСЃР°: Р»РѕРіРѕС‚РёРї, РјРµРЅСЋ, СѓРІРµРґРѕРјР»РµРЅРёСЏ, РїСЂРѕС„РёР»СЊ.
 *
 *  РџРѕРёСЃРєР° Р·РґРµСЃСЊ Р±РѕР»СЊС€Рµ РЅРµС‚: РѕРЅ РїРµСЂРµРµС…Р°Р» РЅР° СЃС‚СЂР°РЅРёС†С‹ В«РџСЂРѕРіРѕРЅС‹В» Рё В«РњРѕРґРµР»РёВ», РіРґРµ
 *  РёС‰РµС‚ СЃРІРѕРё РґР°РЅРЅС‹Рµ. РћР±С‰РёР№ С„РёР»СЊС‚СЂ РІ С€Р°РїРєРµ Р±С‹Р» РЅРµРІРµСЂРµРЅ вЂ” РѕРЅ РїСЂРёРјРµРЅСЏР»СЃСЏ С‚РѕР»СЊРєРѕ Рє
 *  СЃРїРёСЃРєСѓ РїСЂРѕРіРѕРЅРѕРІ, Р° РЅР° РѕСЃС‚Р°Р»СЊРЅС‹С… СЌРєСЂР°РЅР°С… РїСЂРѕСЃС‚Рѕ Р·Р°РЅРёРјР°Р» РјРµСЃС‚Рѕ.
 *
 *  РџСЂР°РІРёР»Р° РїРѕРІРµРґРµРЅРёСЏ, Р·Р°РєСЂРµРїР»С‘РЅРЅС‹Рµ Р·Р°РјРµСЂРѕРј:
 *
 *  1. РћС‚РєСЂС‹С‚ РјР°РєСЃРёРјСѓРј РћР”РРќ РїРѕРїРѕРІРµСЂ. Р Р°РЅСЊС€Рµ РјРµРЅСЋ СЏР·С‹РєР° Р¶РёР»Рѕ СЃРІРѕРёРј СЃРѕСЃС‚РѕСЏРЅРёРµРј
 *     РІРЅСѓС‚СЂРё LanguageSwitcher, РїРѕСЌС‚РѕРјСѓ РєР»РёРє РїРѕ РєРѕР»РѕРєРѕР»СЊС‡РёРєСѓ РѕСЃС‚Р°РІР»СЏР» РµРіРѕ
 *     РѕС‚РєСЂС‹С‚С‹Рј вЂ” РЅР° СЌРєСЂР°РЅРµ Р±С‹Р»Рѕ РґРІР° РјРµРЅСЋ, Р° Escape Р·Р°РєСЂС‹РІР°Р» РЅРµ РІСЃС‘.
 *
 *  2. Escape Р·Р°РєСЂС‹РІР°РµС‚ Р»СЋР±РѕР№ РїРѕРїРѕРІРµСЂ. */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth, can } from '../auth'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'
import LanguageSwitcher from '../components/LanguageSwitcher'
import TopNav from '../components/TopNav'
import markUrl from '../assets/cybra-mark.png'
import wordmarkUrl from '../assets/cybra-wordmark.png'
import {
  ArrowSquareOut, Bell, CaretDown, SignOut, UserCircle,
} from '../icons'

export default function Topbar() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const runs = useApi(() => api.runs(50))
  const { t } = useI18n()
  const [panel, setPanel] = useState(null) // 'bell' | 'account' | 'lang' | null
  const wrapRef = useRef(null)
  // РЎРЅРёРјРѕРє id СѓРІРµРґРѕРјР»РµРЅРёР№, РєРѕС‚РѕСЂС‹Рµ С‡РµР»РѕРІРµРє СѓР¶Рµ РІРёРґРµР». РҐСЂР°РЅРёС‚СЃСЏ РІ localStorage,
  // С‡С‚РѕР±С‹ РёРЅРґРёРєР°С‚РѕСЂ РЅРµ Р·Р°РіРѕСЂР°Р»СЃСЏ Р·Р°РЅРѕРІРѕ РїСЂРё РєР°Р¶РґРѕР№ РїРµСЂРµР·Р°РіСЂСѓР·РєРµ СЃС‚СЂР°РЅРёС†С‹:
  // В«РЅРµРїСЂРѕС‡РёС‚Р°РЅРѕВ» вЂ” СЌС‚Рѕ СЃРІРѕР№СЃС‚РІРѕ СЃРѕР±С‹С‚РёСЏ, Р° РЅРµ СЃРµСЃСЃРёРё Р±СЂР°СѓР·РµСЂР°.
  const [seenIds, setSeenIds] = useState(() => {
    try {
      const raw = window.localStorage.getItem('cybra.seen-alerts')
      return raw ? new Set(JSON.parse(raw)) : new Set()
    } catch {
      return new Set()
    }
  })

  const initials = (user?.display_name || user?.email || 'AD').slice(0, 2).toUpperCase()
  const name = user?.display_name || user?.email || ''

  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') setPanel(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    function onDown(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setPanel(null)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const alerts = (runs.data || []).filter((run) =>
    ['PARTIAL', 'ERROR', 'CANCELLED'].includes(run.status),
  )

  // РќРѕРІС‹Рµ вЂ” С‚Рµ, С‡С‚Рѕ РїРѕСЏРІРёР»РёСЃСЊ РїРѕСЃР»Рµ РїСЂРѕС€Р»РѕРіРѕ РѕС‚РєСЂС‹С‚РёСЏ РјРµРЅСЋ.
  const freshAlerts = alerts.filter((run) => !seenIds.has(run.id))
  const hasFresh = freshAlerts.length > 0

  /** Р—Р°РїРѕРјРЅРёС‚СЊ С‚РµРєСѓС‰РёР№ РЅР°Р±РѕСЂ РєР°Рє РїСЂРѕСЃРјРѕС‚СЂРµРЅРЅС‹Р№ Рё РїРѕРіР°СЃРёС‚СЊ РёРЅРґРёРєР°С‚РѕСЂ. */
  function markAlertsSeen() {
    const ids = new Set(alerts.map((run) => run.id))
    setSeenIds(ids)
    try {
      window.localStorage.setItem('cybra.seen-alerts', JSON.stringify([...ids]))
    } catch {
      // РџСЂРёРІР°С‚РЅС‹Р№ СЂРµР¶РёРј РёР»Рё Р·Р°РїСЂРµС‰С‘РЅРЅРѕРµ С…СЂР°РЅРёР»РёС‰Рµ: РёРЅРґРёРєР°С‚РѕСЂ РїСЂРѕСЃС‚Рѕ РЅРµ
      // Р·Р°РїРѕРјРЅРёС‚СЃСЏ РјРµР¶РґСѓ РїРµСЂРµР·Р°РіСЂСѓР·РєР°РјРё, РЅРѕ РёРЅС‚РµСЂС„РµР№СЃ РїСЂРѕРґРѕР»Р¶РёС‚ СЂР°Р±РѕС‚Р°С‚СЊ.
    }
  }

  /** Р•РґРёРЅСЃС‚РІРµРЅРЅР°СЏ С‚РѕС‡РєР° РїРµСЂРµРєР»СЋС‡РµРЅРёСЏ РїРѕРїРѕРІРµСЂРѕРІ вЂ” РіР°СЂР°РЅС‚РёСЂСѓРµС‚ В«РѕРґРёРЅ Р·Р° СЂР°Р·В». */
  function togglePanel(which) {
    setPanel((current) => (current === which ? null : which))
  }

  return (
    <div className="topbar" ref={wrapRef}>
      <div className="topbar-brand">
        {/* Р¤РёСЂРјРµРЅРЅС‹Р№ Р·РЅР°Рє Рё РЅР°РґРїРёСЃСЊ вЂ” СЂР°СЃС‚СЂРѕРІС‹Рµ Р°СЃСЃРµС‚С‹ РёР· docs/brand,
            РѕР±СЂРµР·Р°РЅРЅС‹Рµ РїРѕ Р°Р»СЊС„Рµ Рё СЃРѕС…СЂР°РЅС‘РЅРЅС‹Рµ РІ 3x (СЃРј. scripts/prep_brand_assets.py).
            РљР°СЂС‚РёРЅРєР°, Р° РЅРµ РёРЅР»Р°Р№РЅ-SVG: Р»РѕРіРѕС‚РёРї РѕР±СЉС‘РјРЅС‹Р№, СЃ РіСЂР°РґРёРµРЅС‚Р°РјРё
            РјРµС‚Р°Р»Р»Р°, вЂ” С‚СЂР°СЃСЃРёСЂРѕРІРєР° РІ SVG РїРѕС‚РµСЂСЏР»Р° Р±С‹ СЌС‚Рё РїРµСЂРµС…РѕРґС‹ Рё РґР°Р»Р° Р±С‹
            СЃС‚СѓРїРµРЅС‡Р°С‚С‹Рµ РєСЂР°СЏ. Р—РЅР°Рє Рё РЅР°РґРїРёСЃСЊ Р»РµР¶Р°С‚ РѕС‚РґРµР»СЊРЅС‹РјРё С„Р°Р№Р»Р°РјРё, С‡С‚РѕР±С‹
            РёС… РјРѕР¶РЅРѕ Р±С‹Р»Рѕ РїРѕР·РёС†РёРѕРЅРёСЂРѕРІР°С‚СЊ РЅРµР·Р°РІРёСЃРёРјРѕ. */}
        <img
          className="brand-logo"
          src={markUrl}
          alt=""
          aria-hidden="true"
        />
        <div className="brand-text">
          <img
            className="brand-wordmark-img"
            src={wordmarkUrl}
            alt="CYBRA"
          />
          <div className="brand-sub">security console</div>
        </div>
      </div>

      <div className="topbar-center">
        <div className="topbar-center-inner">
          <TopNav />
        </div>
      </div>

      <div className="topbar-actions">
        <LanguageSwitcher
          open={panel === 'lang'}
          onToggle={(next) => setPanel(next ? 'lang' : null)}
        />

        <div style={{ position: 'relative' }}>
          <button
            className={`icon-btn bell-btn${panel === 'bell' ? ' is-open' : ''}`}
            aria-label={
              t('РЈРІРµРґРѕРјР»РµРЅРёСЏ')
              + (hasFresh ? `: ${t('РЅРѕРІС‹С…')} ${freshAlerts.length}` : '')
            }
            aria-expanded={panel === 'bell'}
            onClick={() => {
              togglePanel('bell')
              // РћС‚РјРµС‚РєСѓ СЃС‚Р°РІРёРј РїСЂРё РѕС‚РєСЂС‹С‚РёРё, Р° РЅРµ РїСЂРё Р·Р°РєСЂС‹С‚РёРё: РёРЅР°С‡Рµ Р·РЅР°С‡РѕРє
              // РѕСЃС‚Р°С‘С‚СЃСЏ Р±РµР»С‹Рј, РїРѕРєР° РјРµРЅСЋ РѕС‚РєСЂС‹С‚Рѕ, Рё С‡РµР»РѕРІРµРє РЅРµ РїРѕРЅРёРјР°РµС‚,
              // РїСЂРѕС‡РёС‚Р°Р» РѕРЅ СѓРІРµРґРѕРјР»РµРЅРёРµ РёР»Рё РЅРµС‚.
              if (panel !== 'bell') markAlertsSeen()
            }}
          >
            {/* Р—РЅР°С‡РѕРє РІСЃРµРіРґР° СЏРЅС‚Р°СЂРЅС‹Р№ вЂ” СЌС‚Рѕ РµРіРѕ С€С‚Р°С‚РЅС‹Р№ С†РІРµС‚. РџСЂРёР·РЅР°Рє
                РЅРµРїСЂРѕС‡РёС‚Р°РЅРЅРѕРіРѕ вЂ” С‚РѕР»СЊРєРѕ Р±РµР»Р°СЏ С‚РѕС‡РєР° РІ СѓРіР»Сѓ: РѕР±РІРѕРґРєР° Рё
                СЃРІРµС‡РµРЅРёРµ РїРµСЂРµС‚СЏРіРёРІР°Р»Рё РІРЅРёРјР°РЅРёРµ СЃ СЃР°РјРѕР№ С‚РѕС‡РєРё. */}
            <Bell size={18} weight="bold" />
            {hasFresh ? <span className="fresh-badge" aria-hidden="true" /> : null}
          </button>

          {panel === 'bell' ? (
            <div className="popover" role="menu">
              <div className="popover-head">
                <span>{t('РќРµР·Р°РІРµСЂС€С‘РЅРЅС‹Рµ РїСЂРѕРіРѕРЅС‹')}</span>
                <span className={`popover-count${alerts.length ? ' is-active' : ''}`}>
                  {alerts.length}
                </span>
              </div>
              {alerts.length === 0 ? (
                /* РџСѓСЃС‚РѕРµ СЃРѕСЃС‚РѕСЏРЅРёРµ РѕР±СЉСЏСЃРЅСЏРµС‚, С‡С‚Рѕ Р·РґРµСЃСЊ РїРѕСЏРІРёС‚СЃСЏ: Р±РµР· СЌС‚РѕРіРѕ
                   РјРµРЅСЋ РІС‹РіР»СЏРґРµР»Рѕ РєР°Рє РЅРµР·Р°РєРѕРЅС‡РµРЅРЅР°СЏ Р·Р°РіРѕС‚РѕРІРєР°. */
                <div className="popover-blank">
                  <span className="popover-blank-ico">
                    <Bell size={17} weight="bold" />
                  </span>
                  <span className="popover-blank-title">
                    {t('РќРµС‚ РЅРµР·Р°РІРµСЂС€С‘РЅРЅС‹С… РїСЂРѕРіРѕРЅРѕРІ')}
                  </span>
                  <span className="popover-blank-hint">
                    {t('Р—РґРµСЃСЊ РїРѕСЏРІСЏС‚СЃСЏ РїСЂРѕРіРѕРЅС‹ СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј PARTIAL, ERROR РёР»Рё CANCELLED.')}
                  </span>
                </div>
              ) : (
                alerts.slice(0, 6).map((run) => (
                  <button
                    key={run.id}
                    className="popover-item"
                    onClick={() => {
                      setPanel(null)
                      navigate(`/runs/${run.id}`)
                    }}
                  >
                    <span className="popover-label">{run.label}</span>
                    <span className={`pill ${run.status === 'ERROR' ? 'bad' : 'warn'}`}>
                      {run.status}
                    </span>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>

        <div style={{ position: 'relative' }}>
          <button
            className={`profile-btn${panel === 'account' ? ' is-open' : ''}`}
            aria-label={t('РђРєРєР°СѓРЅС‚')}
            aria-expanded={panel === 'account'}
            onClick={() => togglePanel('account')}
          >
            <span className="avatar">{initials}</span>
            {/* Р РѕР»СЊ СѓР±СЂР°РЅР° РёР· РєРЅРѕРїРєРё: РѕРЅР° РґСѓР±Р»РёСЂРѕРІР°Р»Р° СЃС‚СЂРѕРєСѓ РЅРёР¶Рµ РІ РјРµРЅСЋ Рё
                СЂР°СЃС‚СЏРіРёРІР°Р»Р° РєР°РїСЃСѓР»Сѓ РїРѕ РІС‹СЃРѕС‚Рµ. */}
            <span className="profile-name">{name}</span>
            <CaretDown size={11} weight="bold" className="profile-caret" />
          </button>

          {panel === 'account' ? (
            <div className="popover popover-account" role="menu">
              <div className="account-head">
                <span className="avatar avatar-lg">{initials}</span>
                <span className="account-text">
                  <span className="account-name">{name}</span>
                  <span className="account-mail">{user?.email}</span>
                  <span className="account-role">{user?.role}</span>
                </span>
              </div>
              <div className="popover-sep" />
              <button
                className="popover-item"
                onClick={() => {
                  setPanel(null)
                  navigate('/settings')
                }}
              >
                <span className="popover-row">
                  <UserCircle size={14} weight="bold" />
                  {t('РќР°СЃС‚СЂРѕР№РєРё')} Рё {t('РїР°СЂРѕР»СЊ')}
                </span>
              </button>
              {can(user, 'operator') ? (
                <button
                  className="popover-item"
                  onClick={() => {
                    setPanel(null)
                    navigate('/runs/new')
                  }}
                >
                  <span className="popover-row">
                    <ArrowSquareOut size={14} weight="bold" />
                    {t('РќРѕРІС‹Р№ РїСЂРѕРіРѕРЅ')}
                  </span>
                </button>
              ) : null}
              {/* Р Р°Р·РґРµР»РёС‚РµР»СЊ РїРµСЂРµРґ В«Р’С‹Р№С‚РёВ» СѓР±СЂР°РЅ: РѕРЅ РІРёР·СѓР°Р»СЊРЅРѕ СЂР°Р·СЂС‹РІР°Р»
                  РјРµРЅСЋ РїСЂРѕС„РёР»СЏ РЅР° РґРІРµ РЅРµСЃРІСЏР·Р°РЅРЅС‹Рµ С‡Р°СЃС‚Рё. РњРµР¶РґСѓ Р±Р»РѕРєРѕРј
                  Р»РёС‡РЅРѕСЃС‚Рё Рё РґРµР№СЃС‚РІРёСЏРјРё СЂР°Р·РґРµР»РёС‚РµР»СЊ РѕСЃС‚Р°С‘С‚СЃСЏ вЂ” С‚Р°Рј РѕРЅ
                  РѕСЃРјС‹СЃР»РµРЅ, Р° Р·РґРµСЃСЊ РґРµР№СЃС‚РІРёРµ В«РІС‹Р№С‚РёВ» С‚Р°РєРѕРµ Р¶Рµ, РєР°Рє
                  РѕСЃС‚Р°Р»СЊРЅС‹Рµ. */}
              <button className="popover-item danger" onClick={logout}>
                <span className="popover-row">
                  <SignOut size={14} weight="bold" />
                  {t('Р’С‹Р№С‚Рё')}
                </span>
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
