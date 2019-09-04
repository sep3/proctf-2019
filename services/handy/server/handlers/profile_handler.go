package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/gorilla/schema"

	"handy/server/backends"
)

type profileForm struct {
	ID string
}

type profileHandler struct {
	us *backends.UserStorage
}

func NewProfileHandler(us *backends.UserStorage) *profileHandler {
	return &profileHandler{
		us: us,
	}
}

func (h *profileHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		h.handleGet(w, r)
	} else {
		HandleError(w, fmt.Errorf("invalid verb for profile handler: %s", r.Method), http.StatusBadRequest)
	}
}

func (h *profileHandler) handleGet(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		HandleError(w, err, http.StatusBadRequest)
		return
	}

	decoder := schema.NewDecoder()
	pf := &profileForm{}
	if err := decoder.Decode(pf, r.Form); err != nil {
		HandleError(w, fmt.Errorf("failed to parse form: %s", err), http.StatusBadRequest)
		return
	}

	pi, err := h.us.GetProfileInfo(pf.ID)
	if err != nil {
		HandleError(w, fmt.Errorf("failed to get profile info: %s", err), http.StatusBadRequest)
		return
	}

	resultJSON, err := json.Marshal(pi)
	if err != nil {
		HandleError(w, fmt.Errorf("failed to marshal response: %s", err), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(resultJSON)
}
