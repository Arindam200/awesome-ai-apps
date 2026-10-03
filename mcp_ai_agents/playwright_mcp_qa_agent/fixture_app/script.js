const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");

loginForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();

    if (!email) {
        loginError.textContent = "Email is required";
        return;
    }

    if (!password) {
        loginError.textContent = "Password is required";
        return;
    }

    loginError.textContent = "Signed in successfully";
});

const searchForm = document.getElementById("search-form");
const searchResults = document.getElementById("search-results");

searchForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const query = document.getElementById("search").value.trim();

    if (!query) {
        searchResults.textContent = "Please enter a search term";
        return;
    }

    if (query.toLowerCase() === "laptop") {
        searchResults.textContent = "Laptop - ?50,000";
        return;
    }

    searchResults.textContent = "No products found";
});
