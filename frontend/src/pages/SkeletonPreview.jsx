/** ВРЕМЕННАЯ страница: показывает все скелетоны сразу.
 *
 *  Нужна, чтобы посмотреть, как выглядит загрузка, не подлавливая момент
 *  запроса. Удаляется после просмотра — в навигации её нет. */
import { BlockSkeleton, PageSkeleton } from '../components/Skeletons'

const CASES = [
  { variant: 'dashboard', title: 'Дашборд', desc: 'шапка, 4 KPI, график с блоком действий, таблица' },
  { variant: 'runs', title: 'Прогоны', desc: 'шапка и таблица на 7 строк' },
  { variant: 'detail', title: 'Экран прогона', desc: 'шапка, 3 KPI, таблица шагов' },
  { variant: 'datasets', title: 'Датасеты', desc: 'шапка, колонка версий и панель кейсов' },
  { variant: 'metrics', title: 'Метрики', desc: 'шапка, карточка фильтров, 3 KPI, график' },
  { variant: 'form', title: 'Новый прогон', desc: 'шапка и две колонки формы' },
  { variant: 'default', title: 'Настройки / отчёт', desc: 'шапка и две карточки' },
]

export default function SkeletonPreview() {
  return (
    <div className="fade-in">
      <div className="page-head" style={{ marginBottom: 10 }}>
        <div>
          <h1>Скелетоны загрузки</h1>
          <p>
            Временная страница: все варианты сразу, без ожидания API. Каждый блок
            переливается между #26262b и #303036.
          </p>
        </div>
      </div>

      {CASES.map((item) => (
        <section key={item.variant} style={{ marginTop: 34 }}>
          <div className="card-head" style={{ marginBottom: 12 }}>
            <div>
              <h2>{item.title}</h2>
              <div className="dim" style={{ fontSize: 11.5, marginTop: 2 }}>
                variant=&quot;{item.variant}&quot; · {item.desc}
              </div>
            </div>
          </div>
          <div
            style={{
              border: '1px dashed var(--edge)',
              borderRadius: 12,
              padding: 18,
              background: 'var(--ink-900)',
            }}
          >
            <PageSkeleton variant={item.variant} />
          </div>
        </section>
      ))}

      <section style={{ marginTop: 34 }}>
        <div className="card-head" style={{ marginBottom: 12 }}>
          <div>
            <h2>Блочный скелетон</h2>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 2 }}>
              для мест внутри уже загруженной страницы: кейсы датасета, шаги прогона, график
            </div>
          </div>
        </div>
        <div
          style={{
            border: '1px dashed var(--edge)',
            borderRadius: 12,
            padding: 18,
            background: 'var(--ink-900)',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 16,
          }}
        >
          <div className="card">
            <div className="card-head">
              <h2>Кейсы</h2>
            </div>
            <BlockSkeleton rows={5} />
          </div>
          <div className="card">
            <div className="card-head">
              <h2>Динамика</h2>
            </div>
            <BlockSkeleton rows={5} height={220} />
          </div>
        </div>
      </section>
    </div>
  )
}
