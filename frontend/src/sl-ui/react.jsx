// React adapters over SL UI Library.
//
// The library exports vanilla controllers (window.SLComponent.mount), not React
// components. Wrapping them keeps the original controller, its motion and its
// accessibility behaviour intact, which is what the library's integration guide
// asks for ("mount the vanilla controller after its DOM exists, call destroy()
// when removing it").

import { useEffect, useRef } from 'react'

/** The library's everyday-button, themed to colour and a Phosphor icon. */
export function SlButton({ icon: Icon, label, onClick, disabled, tone = 'default' }) {
  const host = useRef(null)
  return (
    <button
      type="button"
      className={`btn ${tone}`}
      onClick={onClick}
      disabled={disabled}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
    >
      {Icon ? <Icon size={15} weight="bold" /> : null}
      {label}
    </button>
  )
}

/**
 * Mounts one of the library's vanilla controllers into a React-owned host node.
 * `mount` receives the element and a factory returning the controller; the
 * effect tears it down on unmount, which is the contract the library documents.
 */
export function SlMount({ mount, deps = [], className = '' }) {
  const host = useRef(null)
  const instance = useRef(null)

  useEffect(() => {
    if (!host.current) return undefined
    instance.current = mount(host.current)
    return () => {
      instance.current?.destroy?.()
      instance.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return <div ref={host} className={`sl-component ${className}`} />
}

/**
 * Builds a library text field from its documented markup:
 * .sl-field > .sl-field__control > input + label.
 * Using the same class names means the vendored CSS applies unchanged.
 */
export function SlTextField({ label, value, onChange, type = 'text', help, placeholder = ' ', id }) {
  const inputId = id || `sl-${label.replace(/\s+/g, '-').toLowerCase()}`
  return (
    <div className="sl-field">
      <div className="sl-field__control">
        <input
          id={inputId}
          className="sl-field__input"
          type={type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          aria-describedby={help ? `${inputId}-help` : undefined}
        />
        <label className="sl-field__label" htmlFor={inputId}>
          {label}
        </label>
      </div>
      {help ? (
        <p className="sl-field__helper" id={`${inputId}-help`}>
          {help}
        </p>
      ) : null}
    </div>
  )
}
