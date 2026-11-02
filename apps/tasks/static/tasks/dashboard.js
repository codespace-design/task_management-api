const taskList = document.querySelector("#task-list");
const emptyState = document.querySelector("#empty-state");
const emptyTitle = document.querySelector("#empty-title");
const emptyDescription = document.querySelector("#empty-description");
const errorMessage = document.querySelector("#error-message");
const searchInput = document.querySelector("#task-search");
const filterSelect = document.querySelector("#task-filter");
const taskDialog = document.querySelector("#task-dialog");
const taskForm = document.querySelector("#task-form");
const titleInput = document.querySelector("#task-title");
const descriptionInput = document.querySelector("#task-description");
const dialogTitle = document.querySelector("#dialog-title");
const saveButton = document.querySelector("#save-task");
const formError = document.querySelector("#form-error");

let tasks = [];
let editingTaskId = null;

const apiUrl = "/api/tasks/";

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function clearError() {
  errorMessage.textContent = "";
  errorMessage.hidden = true;
}

function setFormError(message) {
  formError.textContent = message;
  formError.hidden = !message;
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status}). Please try again.`;
    try {
      const body = await response.json();
      const detail = body.detail || body.title?.[0] || body.non_field_errors?.[0];
      if (detail) message = detail;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function createButton(label, className, text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.setAttribute("aria-label", label);
  button.title = label;
  button.textContent = text;
  return button;
}

function createTaskCard(task) {
  const card = document.createElement("article");
  card.className = `task-card${task.completed ? " is-completed" : ""}`;
  card.dataset.taskId = task.id;

  const checkButton = createButton(
    task.completed ? "Mark as in progress" : "Mark as completed",
    "task-check",
    "✓",
  );
  checkButton.dataset.action = "toggle";
  checkButton.setAttribute("aria-pressed", String(task.completed));

  const copy = document.createElement("div");
  copy.className = "task-copy";
  const title = document.createElement("h3");
  title.className = "task-title";
  title.textContent = task.title;
  copy.append(title);
  if (task.description) {
    const description = document.createElement("p");
    description.className = "task-description";
    description.textContent = task.description;
    copy.append(description);
  }

  const meta = document.createElement("div");
  meta.className = "task-meta";
  const status = document.createElement("span");
  status.className = "task-status";
  status.textContent = task.completed ? "Completed" : "In progress";
  const separator = document.createElement("span");
  separator.textContent = "·";
  const date = document.createElement("time");
  date.dateTime = task.updated_at;
  date.textContent = `Updated ${formatDate(task.updated_at)}`;
  meta.append(status, separator, date);
  copy.append(meta);

  const actions = document.createElement("div");
  actions.className = "task-actions";
  const editButton = createButton("Edit task", "icon-button", "✎");
  editButton.dataset.action = "edit";
  const deleteButton = createButton("Delete task", "icon-button delete-button", "×");
  deleteButton.dataset.action = "delete";
  actions.append(editButton, deleteButton);
  card.append(checkButton, copy, actions);
  return card;
}

function updateStats() {
  const completed = tasks.filter((task) => task.completed).length;
  document.querySelector("#total-count").textContent = tasks.length;
  document.querySelector("#active-count").textContent = tasks.length - completed;
  document.querySelector("#completed-count").textContent = completed;
}

function renderTasks() {
  const query = searchInput.value.trim().toLocaleLowerCase();
  const filter = filterSelect.value;
  const visibleTasks = tasks.filter((task) => {
    const matchesText = `${task.title} ${task.description}`.toLocaleLowerCase().includes(query);
    const matchesFilter = filter === "all" || (filter === "completed" ? task.completed : !task.completed);
    return matchesText && matchesFilter;
  });

  taskList.replaceChildren(...visibleTasks.map(createTaskCard));
  document.querySelector("#visible-count").textContent = visibleTasks.length;
  emptyState.hidden = visibleTasks.length > 0;
  if (tasks.length === 0) {
    emptyTitle.textContent = "Your list is a blank canvas";
    emptyDescription.textContent = "Add a task and make today count.";
  } else {
    emptyTitle.textContent = query || filter !== "all" ? "No tasks match this view" : "You’re all caught up";
    emptyDescription.textContent = query || filter !== "all"
      ? "Try another search or choose a different filter."
      : "A little breathing room looks good on you.";
  }
}

async function loadTasks() {
  taskList.setAttribute("aria-busy", "true");
  clearError();
  try {
    tasks = await request(apiUrl);
    updateStats();
    renderTasks();
  } catch (error) {
    showError(`Could not load tasks. ${error.message}`);
  } finally {
    taskList.setAttribute("aria-busy", "false");
  }
}

function openDialog(task = null) {
  editingTaskId = task?.id ?? null;
  dialogTitle.textContent = task ? "Edit your task" : "Create a task";
  saveButton.innerHTML = task ? "Save changes <span aria-hidden=\"true\">↗</span>" : "Create task <span aria-hidden=\"true\">↗</span>";
  titleInput.value = task?.title ?? "";
  descriptionInput.value = task?.description ?? "";
  setFormError("");
  taskDialog.showModal();
  titleInput.focus();
}

function closeDialog() {
  taskDialog.close();
  taskForm.reset();
  editingTaskId = null;
  setFormError("");
}

async function saveTask(event) {
  event.preventDefault();
  const title = titleInput.value.trim();
  if (!title) {
    setFormError("Please enter a task name.");
    titleInput.focus();
    return;
  }

  saveButton.disabled = true;
  setFormError("");
  const payload = { title, description: descriptionInput.value.trim() };
  if (editingTaskId !== null) payload.completed = tasks.find((task) => task.id === editingTaskId)?.completed ?? false;
  try {
    await request(editingTaskId === null ? apiUrl : `${apiUrl}${editingTaskId}/`, {
      method: editingTaskId === null ? "POST" : "PUT",
      body: JSON.stringify(payload),
    });
    closeDialog();
    await loadTasks();
  } catch (error) {
    setFormError(error.message);
  } finally {
    saveButton.disabled = false;
  }
}

async function handleTaskAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const card = button.closest("[data-task-id]");
  const task = tasks.find((item) => item.id === Number(card.dataset.taskId));
  if (!task) return;

  if (button.dataset.action === "edit") {
    openDialog(task);
    return;
  }
  if (button.dataset.action === "delete") {
    if (!window.confirm(`Delete “${task.title}”? This cannot be undone.`)) return;
    button.disabled = true;
    try {
      await request(`${apiUrl}${task.id}/`, { method: "DELETE" });
      tasks = tasks.filter((item) => item.id !== task.id);
      updateStats();
      renderTasks();
      clearError();
    } catch (error) {
      showError(`Could not delete the task. ${error.message}`);
      button.disabled = false;
    }
    return;
  }
  if (button.dataset.action === "toggle") {
    button.disabled = true;
    try {
      const updatedTask = await request(`${apiUrl}${task.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ completed: !task.completed }),
      });
      tasks = tasks.map((item) => item.id === updatedTask.id ? updatedTask : item);
      updateStats();
      renderTasks();
      clearError();
    } catch (error) {
      showError(`Could not update the task. ${error.message}`);
      button.disabled = false;
    }
  }
}

document.querySelector("#today-label").textContent = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  month: "short",
  day: "numeric",
}).format(new Date());
document.querySelector("#open-create").addEventListener("click", () => openDialog());
document.querySelector("#empty-create").addEventListener("click", () => openDialog());
document.querySelector("#close-dialog").addEventListener("click", closeDialog);
document.querySelector("#cancel-dialog").addEventListener("click", closeDialog);
taskForm.addEventListener("submit", saveTask);
taskList.addEventListener("click", handleTaskAction);
searchInput.addEventListener("input", renderTasks);
filterSelect.addEventListener("change", renderTasks);
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !taskDialog.open && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    searchInput.focus();
  }
  if (event.key === "Escape" && taskDialog.open) closeDialog();
});

loadTasks();
