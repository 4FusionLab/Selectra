# Selectra: возможности Fusion API и границы реализации

Исследование: 25 октября 2026 года. Цель — команда `Select Similar` для BRep-рёбер и граней с автоматическим выбором наиболее вероятного смысла сходства.

Правило пользователя: поиск только внутри тела выбранного примера. Оно действует и после добавления component occurrences: областью остаётся конкретное тело выбранного экземпляра, а не все тела компонента или документа.

Основания: официальная документация Autodesk и Blender, определения API из установленного Fusion (`~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Python/defs/adsk/core.py` и `fusion.py`). Context7 найден по ID `/autodeskfusion360/autodeskfusion360.github.io`, но его выдача по конкретным событиям и BRep недостаточна; детали ниже проверены непосредственно по первичным источникам. Это исследование API, а не приёмка работающего дополнения. Живой Fusion в ходе исследования не использовался.

## 1. Контекстное меню и исходный выбор

`UserInterface.markingMenuDisplaying` вызывается перед отображением круглого marking menu и вертикального контекстного меню. Через `linearMarkingMenu.controls.addCommand(...)` можно добавить свою команду. Для Selectra достаточно дописать один пункт в существующее меню. Официальный пример очищает меню для демонстрации API; повторять это поведение в продукте не требуется. [Событие](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_UserInterface_markingMenuDisplaying.htm), [пример Autodesk](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/MarkingMenuSample_Sample.htm).

`MarkingMenuEventArgs.selectedEntities` даёт контекст меню и может оказаться пустым. Это не основание считать, что API уже восстановил полный пользовательский замысел или что наведённая сущность равна исходному множественному выбору. `UserInterface.activeSelections` представляет текущее выделение. Практическое решение: сохранять валидные исходные объекты на открытии меню, проверять тип и область, перед запуском команды повторно проверять документ и валидность. [Контекст меню](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_MarkingMenuEventArgs_selectedEntities.htm), [activeSelections](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_UserInterface_activeSelections.htm).

`activeSelectionChanged` относится только к штатной команде Select. Он не является универсальным перехватчиком выбора внутри Fillet, Chamfer и других команд. [Ограничение события](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_UserInterface_activeSelectionChanged.htm).

## 2. Предпросмотр и перенос результата

Есть два разных множества: глобальное `activeSelections` и выбор конкретного `SelectionCommandInput`. Глобальные `Selections.add`/`clear` позволяют управлять видимым выделением; `add` возвращает признак успеха. Выбор внутри своей команды следует заполнять через её собственный input. [Selections.add](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Selections_add.htm), [Selections.clear](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Selections_clear.htm).

`SelectionCommandInput.addSelection` запрещён в `commandCreated`; допустим в `activate` и позже. Нужно проверять результат добавления: фильтры и лимиты могут его отклонить. Свойство `isUseCurrentSelections` по состоянию проверенной документации помечено Preview, Autodesk не рекомендует распространять программы на preview API. Для первого продукта опираться на стабильные события и методы, без установки этого свойства. [addSelection](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_SelectionCommandInput_addSelection.htm), [статус isUseCurrentSelections](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_SelectionCommandInput_isUseCurrentSelections.htm).

Предлагаемый жизненный цикл прототипа:

1. В меню сохранить исходные сущности и документ; создать собственную команду.
2. В `activate` заполнить input результата вычисленным набором. В `preSelect` ограничить ручные изменения результата; уточнение исходных примеров — отдельная будущая функция.
3. При изменении уровня сходства пересчитать набор и обновить input в том же диалоге.
4. В `execute` сохранить подтверждённый набор, в `destroy` запланировать перенос; при отмене планировать восстановление исходного выбора.
5. В обработчике отложенного события проверить тот же активный документ, отсутствие другой пользовательской команды, валидность объектов; затем применить выбор с проверкой каждого `add`. Не перехватывать управление у команды, которую пользователь успел открыть.

Это проектное решение, требующее проверки в Fusion. `destroy` подтверждает уничтожение команды; `fireCustomEvent` ставит обработку в очередь основного потока при idle. Успех `fireCustomEvent` означает только постановку в очередь. Он не доказывает, что нужная команда уже стала активной или выделение сохранилось. Дополнительно рассмотреть `isExecutedWhenPreEmpted=False`, чтобы запуск другой команды не стал неявным подтверждением. [destroy](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Command_destroy.htm), [terminationReason](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_CommandEventArgs_terminationReason.htm), [fireCustomEvent](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application_fireCustomEvent.htm), [поведение при прерывании](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Command_isExecutedWhenPreEmpted.htm).

API не даёт оснований обещать универсальную вставку результатов в чужой открытый диалог Fillet/Chamfer. Первая версия: самостоятельная команда из Select, затем пользователь запускает штатную операцию с полученным выбором. Для интеграции внутри чужих команд нужна отдельная проверка поддерживаемых путей.

## 3. Доступные признаки

| Объект | Подтверждённые данные API | Применение в Selectra |
| --- | --- | --- |
| Ребро | `length`, `geometry`, `faces`, `tangentiallyConnectedEdges` | Длина, класс кривой, радиус окружности/дуги, направление прямой, соседство, связная касательная цепь |
| Грань | `area`, `geometry`, `edges`, `loops`, `evaluator`, `pointOnFace`, `tangentiallyConnectedFaces` | Площадь, периметр, тип поверхности, радиус цилиндра, топология границы, направление плоскости, касательная связность |
| Аналитическая геометрия | `Circle3D.radius/normal`, `Arc3D.radius/normal`, `Cylinder.radius/axis`, `Plane.normal/origin` | Признаки, устойчивые к параметризации кривой или поверхности |
| Тело | `isVisible`, `isSelectable` | Исключение выключенных и запрещённых для выбора тел |

Источники таблицы: [BRepEdge](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepEdge.htm), [BRepFace](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepFace.htm), [Circle3D](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Circle3D.htm), [Arc3D](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Arc3D.htm), [Cylinder](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Cylinder.htm), [Plane](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Plane.htm), [видимость тела](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepBody_isVisible.htm), [доступность выбора тела](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepBody_isSelectable.htm).

`BRepEdge.length` задана в сантиметрах, `BRepFace.area` — в квадратных сантиметрах. В ядре хранить эти единицы, для пользовательских подписей преобразовывать явно. Периметр грани — вычисляемый признак по её граничным рёбрам, не отдельное обещанное свойство площади. [Длина](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepEdge_length.htm), [площадь](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepFace_area.htm).

### Нормали и кривые поверхности

`pointOnFace` гарантированно находится внутри границ грани вне граничных рёбер; `face.evaluator` учитывает топологическую обрезку. `getNormalAtPoint` возвращает нормаль в конкретной точке и признак успеха. Для плоскости одна нормаль описывает направление всей поверхности; для цилиндра, сферы или NURBS это локальная характеристика. Нельзя сравнивать произвольные нормали двух цилиндров как их глобальное направление: здесь информативнее ось цилиндра. [pointOnFace](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepFace_pointOnFace.htm), [evaluator](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepFace_evaluator.htm), [getNormalAtPoint](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_SurfaceEvaluator_getNormalAtPoint.htm).

При использовании нормали базовой поверхности учитывать `isParamReversed`. Нормаль face evaluator и нормаль underlying geometry нельзя автоматически считать одинаково ориентированными; конкретный путь получения нормали проверить на внутренних и внешних гранях. [isParamReversed](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepFace_isParamReversed.htm).

Вывод для алгоритма: одинаковый радиус цилиндрической поверхности ещё не отличает отверстие от наружного вала и не доказывает одинаковую глубину. Для семантики «такие же отверстия» потребуются ориентация грани относительно радиального направления, соседние поверхности и граничные петли. Пока такой классификатор не принят на CAD-примерах, подпись должна говорить «цилиндрические грани такого же радиуса». Для свободных поверхностей нельзя обещать сходство формы только по площади и bbox; нужны выборки и отдельные метрики.

## 4. Сборки и идентичность

Объект в компоненте и его отображение в occurrence — разные контексты. Прокси несёт путь occurrence; геометрические запросы к корректному прокси возвращают данные в контексте сборки. Сброс через `nativeObject` убирает этот контекст и может смешать одинаковые детали, находящиеся в разных местах и поворотах. Для будущего сравнения в сборке сохранять исходный proxy и единый корневой контекст; `createForAssemblyContext` использовать осознанно. [Components and Proxies](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ComponentsProxies_UM.htm), [BRepFace.createForAssemblyContext](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepFace_createForAssemblyContext.htm).

Строка `entityToken` может изменяться для той же сущности. Autodesk прямо запрещает определять идентичность сравнением строк: сначала разрешить через `Design.findEntityByToken`, затем сравнивать сущности. Токен не следует использовать как постоянный hash геометрии. `tempId` действует только пока документ открыт и тело не изменено. [entityToken](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepFace_entityToken.htm), [BRepEdge.tempId](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepEdge_tempId.htm).

Первую CAD-приёмку упростить до одного BRep-тела корневого компонента; сборки отложить до тестов с повернутыми, вложенными и повторными occurrences. Идентификаторы чистого ядра — локальные ключи одного снимка, без обещания пережить редактирование модели.

## 5. Отличия от Blender и штатные возможности Fusion

В Blender Select Similar пользователь выбирает свойство: для рёбер доступны длина и направление, для граней — площадь, периметр и нормаль; есть порог сравнения и отдельный поиск похожих регионов по топологии. Это полезный каталог сценариев, но не механизм автоматического определения намерения. Blender работает здесь с polygon mesh; CAD BRep содержит обрезанные аналитические и NURBS-поверхности, поэтому параметры вроде количества сторон полигона или UV seam не имеют прямого универсального соответствия. [Blender Select Similar](https://docs.blender.org/manual/en/latest/modeling/meshes/selecting/similar.html).

Fusion уже имеет Selection Sets и в отдельных рабочих пространствах — специальные средства выбора; Fillet/Chamfer могут автоматически продолжать выбор по Tangent Chain. Selectra должна давать сходство между несвязанными участками и вывод смысла по примерам, а не выдавать штатную касательную цепь за новую уникальную функцию. [Selection in Fusion](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION.htm), [Tangent Chain](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-REF-TANGENT-CHAIN.htm).

## 6. Инженерные выводы и проверка

Следующее — рекомендации проекта, а не гарантии производительности API:

- Снимок дескрипторов строить один раз на открытие команды, хранить только числа/векторы/категории. Чистое ранжирование запускать без повторных BRep-запросов.
- На открытии меню выполнять только дешёвую проверку типа и контекста. Извлечение геометрии начинать после выбора команды.
- Сначала фильтровать тип, видимость, область и грубые размеры; дорогие normal/curvature выборки оставить на уточнение.
- Нужны лимиты кандидатов и понятное сообщение при превышении. Для больших моделей измерять отдельно извлечение признаков, ранжирование и массовое подсвечивание; Python-скорость не доказывает отзывчивость Fusion.
- Геометрия и топология — основа. Сведения о Hole/Fillet/Pattern в истории допустимы как дополнительный сигнал после проверки: у импортированной STEP-модели нельзя предполагать исходную историю построения.
- Для одного примера показывать разумное предложение и возможность уточнить; для нескольких искать общие признаки и снижать вес различающихся. Оценка уверенности эвристическая, не статистическая вероятность намерения.

**MVP:** самостоятельная команда из default Select, один root BRep body, однородные edges либо faces, аналитические типы и простые числовые признаки, ранжирование нескольких гипотез, контролируемый предпросмотр, OK и Cancel с проверкой сохранения выбора.

**Следующие этапы:** тело внутри component occurrence с сохранением области одного выбранного тела, положительные/отрицательные примеры, топологические регионы, надёжное различение отверстий/валов/скруглений, свободные поверхности, сохранённые пользовательские предпочтения. Интеграция внутрь чужой команды — отдельное исследование.

**Обязательная CAD-приёмка:** настоящее меню ПКМ; одна/несколько исходных сущностей; разные типы геометрии; отсутствие результата; перестановка порядка примеров; повторный запуск; Cancel; прерывание другой командой; смена документа до idle; удалённая/невалидная сущность; сохранение выборки после закрытия Selectra и применение штатной операции. Подтвердить отсутствие изменений тел и таймлайна, измерить задержки. Проверки stubs, локальные unit-тесты и сборка ZIP этого не заменяют.

## 7. Уточнения по результатам нативной разработки

Для сборок числовые свойства читаются с nativeObject в системе компонента, а живые ссылки сохраняют assemblyContext. В мировую систему снимки переводятся через [Occurrence.transform2](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Occurrence_transform2.htm). Exact BRep-копия нативной сущности перед показом в root graphics получает [TemporaryBRepManager.transform](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_TemporaryBRepManager_transform.htm). Отдельно проверены мировые boundingBox заливки и контуров. Изменение матрицы входит в guard результата наряду с ревизией тела. Вложенность определяется полным путём экземпляра, а не совпадением имени компонента или entityToken.

При сборке контура нужно учитывать не только coedge.isOpposedToEdge, но и [BRepEdge.isParamReversed](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepEdge_isParamReversed.htm). На реальных рёбрах параметрическое направление evaluator оказалось противоположным направлению BRep-ребра; для штрихов в возрастающем диапазоне разворот задаётся XOR двух флагов. Проверка непрерывности и замыкания не позволяет передать в matcher границу с ошибочно соединёнными концами.

Геометрическая итерация сверена через Context7, официальные документы и установленные Python definitions. Обрезанные петли читаются через [BRepLoop.coEdges](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepLoop_coEdges.htm), направление coedge учитывается при [CurveEvaluator3D.getStrokes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_CurveEvaluator3D_getStrokes.htm). Материал читается через [BRepBody.pointContainment](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepBody_pointContainment.htm), промежуточные границы — через [Component.findBRepUsingRay](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Component_findBRepUsingRay.htm) с hitPoints, visibleEntitiesOnly=False и последующей фильтрацией именно исходного тела. Повторные пересечения одной грани API возвращает только для первого попадания; ограничение учитывается консервативным отказом при любой промежуточной границе. Числовой допуск лучей и реальная проверка полости записаны в VALIDATION.

Актуальный сценарий — [UX.md](UX.md). Отдельное поле Preview убрано. Examples/Exclude используют SelectionCommandInput; результирующий набор показывается через CustomGraphics и превращается в обычное выделение только после OK. Команда захватывает примеры в `commandStarting`, до переключения штатного Select. [Событие](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_UserInterface_commandStarting.htm).

Колесо возвращено штатной навигации Fusion. `Command.keyDown` и `KeyCodes.PageUpKeyCode/PageDownKeyCode` управляют общим ранжированным диапазоном. Это не графовое соседство. [keyDown](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Command_keyDown.htm).

Графика строится в `executePreview`. Дополнительный `doExecutePreview` поверх автоматического preview при изменении CommandInputs убран: он давал два обновления на одно действие. Валидные графические объекты переиспользуются через isVisible; удаление одной cached BRep-графики ранее приводило к недействительным соседним wrappers. На OK/Cancel удаляется вся временная группа.

Magenta-наложение использует `CustomGraphicsShowThroughColorEffect` и depthPriority. Это предотвращает конкуренцию совпадающей временной поверхности с исходной без смещения CAD-геометрии; скрытые совпадения показываются полупрозрачно. В установленном SDK эффект назначается свойству `color`, как остальные CustomGraphicsColorEffect; описание фабрики в документации упоминает showThrough, которого нет в проверенных Python definitions. [Фабрика эффекта](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_CustomGraphicsShowThroughColorEffect_create.htm).

Для нативных событий дополнение запускается как зарегистрированный add-in через Scripts API. Временный импорт entry point из MCP не заменяет этот жизненный цикл. [Scripts.addExisting](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Scripts_addExisting.htm).

При завершении набор фиксируется в execute, графика удаляется в destroy, затем короткий Timer только вызывает `fireCustomEvent`; обращения к модели остаются на основном потоке. В проверенном Fusion 2706.1.14 fireCustomEvent возвращал false, хотя callback выполнялся. Фактический успех подтверждается readback `activeSelections`, а не этим возвращаемым значением.

## Триангуляция криволинейных групп, 26.10.2026

Context7 `/autodeskfusion360/autodeskfusion360.github.io` не покрывает конкретные операции MeshManager, поэтому они дополнительно сверены по установленным Python definitions и официальным документам Autodesk: [createMeshCalculator](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_MeshManager_createMeshCalculator.htm), [TriangleMeshCalculator](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_TriangleMeshCalculator.htm), [nodeIndices](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_TriangleMesh_nodeIndices.htm). Это стабильный API, доступный с августа 2014; Preview API не используется.

`BRepFace.meshManager.createMeshCalculator()` создаёт калькулятор, `surfaceTolerance` задаёт максимальное отклонение сетки в cm, `calculate()` возвращает TriangleMesh. Читаются nodeCoordinates, nodeIndices и normalVectors. Вычисления выполняются на nativeObject, точки и векторы переводятся в мировую систему occurrence.transform2. Созданная сетка не добавляется в документ; временная геометрия служит числовому снимку. На нативной копии пазов подтверждены нормали, NURBS/цилиндры, соответствие preview и OK, отсутствие остаточной графики.

## Топологические петли Select Chain, 26.10.2026

Context7 не дал покрытия по конкретным BRepLoop-методам. По [BRepLoop](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepLoop.htm) и [BRepCoEdge.edge](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepCoEdge_edge.htm) сверены coEdges, edges, isOuter, face и переход к базовому ребру. Для рёбер читаются полные петли без повторяющихся швов. Для стенок вдоль петли соседней грани собирается ровно одна противоположная грань каждого ребра; последовательность должна быть замкнута по смежности стенок. Неполные/немногообразные обходы отклоняются.

## Полный контакт тел для Select Chain, 26.10.2026

Context7 не покрыл детали операции; контракт сверён по [TemporaryBRepManager.booleanOperation](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_TemporaryBRepManager_booleanOperation.htm): входы могут быть не только solid, но и гранями для объединения/обрезки; изменяется только временный targetBody. Это используется для проверки полного совпадения граней: разность в обоих направлениях должна быть пустой. Направления наружных нормалей противоположны. Проверка исходных точек относительно поверхности и двустороннее совпадение границ используют строгий допуск 1e-9 cm и дополняют более широкий внутренний допуск ASM. Точки рёбер должны попадать в обрезанные граничные кривые, а не только в общую опорную плоскость. Объёмное пересечение исходных solids исключает контакт; объединение должно давать один lump.

Временные копии переводятся в мировую систему occurrence.transform2. В граф попадают только целиком соприкасающиеся грани; совпадение одного ребра, точки или части грани не создаёт связи. Для обратного сопоставления каждой виртуальной грани/ребра проверяется полное покрытие исходными частями через BRep Difference. Частично сопоставленный контур не применяется. На окружностях после объединения полуокружностей обратный evaluator иногда зажимает параметр в неправильном конце периодического интервала; проверка расстояния до аналитической окружности и последующая полная разность проводов устраняют эту неоднозначность.

Временный union не сохраняется в документе. Перед preview/OK и отложенным переносом выбора проверяются ревизии и позы всех видимых тел, участвовавших в поиске контактов. Ограничения: 128 видимых тел в проверяемой сборке, 16 тел в связанной группе и мягкий бюджет 8 s; лимит даёт явный отказ без частичного контура. Это численно строгая проверка средствами CAD-ядра, не обещание математически нулевого допуска для любых представлений NURBS.

## Допуск BRep-вершины и ранжирование плоских цепочек

Замкнутая петля соседней плоской BRepFace получает её мировую опорную плоскость; геометрия примера читается в той же системе occurrence.transform2. Это применяется как к обычному телу, так и к временно объединённому домену точного контакта. Контуры на неплоских опорных гранях не объявляются плоскими по нескольким случайным точкам.

В нативной детали обнаружена допустимая для ASM вершина, смещённая от аналитической кривой ребра примерно на 1.5e-7 cm. Использовать её в качестве точной пробы самой кривой нельзя: получался ложный отказ совпадающей дуги. Для обратного сопоставления взяты внутренние параметрические точки кривой; полная BRep-разность подтверждает обрезку и покрытие. При проверке точного контакта граней строгие проверки вершин и границ не ослаблены.

## Сохранение исходных контуров при точном контакте

Каталог Chain across contact теперь складывается из двух источников: родные BRepLoop каждого исходного тела и полностью сопоставленные петли временного объединения. Границы Split Body, удалённые в виртуальном union, остаются допустимыми рёбрами родных контуров. Поэтому их нельзя отбрасывать только из-за отсутствия отображения в виртуальной топологии. Требование полного обратного покрытия остаётся обязательным для сквозных вариантов. Все варианты затем фильтруются прохождением через все примеры и дедуплицируются по полному набору исходных сущностей.
