const messages = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#messageInput");
const themeButton = document.querySelector("#themeButton");
const searchInput = document.querySelector("#searchInput");


/*
 * Отправка сообщения.
 *
 * Пока realtime ещё не подключён, поэтому сообщение
 * добавляется непосредственно в DOM.
 *
 * В следующей части этот обработчик будет заменён
 * на Socket.IO event: message:send.
 */
composer.addEventListener("submit", (event) => {
    event.preventDefault();

    const text = input.value.trim();

    if (!text) {
        return;
    }

    const row = document.createElement("div");
    row.className = "message-row outgoing";

    const message = document.createElement("div");
    message.className = "message";

    const paragraph = document.createElement("p");
    paragraph.textContent = text;

    const time = document.createElement("time");

    const now = new Date();

    time.textContent =
        now.toLocaleTimeString(
            "ru-RU",
            {
                hour: "2-digit",
                minute: "2-digit",
            }
        );

    time.innerHTML +=
        ' <span class="checks">✓</span>';

    message.append(
        paragraph,
        time
    );

    row.append(message);
    messages.append(row);

    input.value = "";

    messages.scrollTo({
        top: messages.scrollHeight,
        behavior: "smooth",
    });
});


/*
 * Dark / light theme.
 */
themeButton.addEventListener("click", () => {
    document.body.classList.toggle("light");

    themeButton.textContent =
        document.body.classList.contains("light")
            ? "☾"
            : "☼";
});


/*
 * Простой поиск по списку чатов.
 */
searchInput.addEventListener("input", () => {
    const query =
        searchInput.value
            .trim()
            .toLowerCase();

    document
        .querySelectorAll(".chat")
        .forEach((chat) => {
            const text =
                chat.textContent.toLowerCase();

            chat.style.display =
                !query || text.includes(query)
                    ? ""
                    : "none";
        });
});


/*
 * Автоматически показываем нижнюю часть истории.
 */
messages.scrollTop =
    messages.scrollHeight;
