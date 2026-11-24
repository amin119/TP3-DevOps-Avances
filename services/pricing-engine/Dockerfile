FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -o /pricing-engine .

FROM gcr.io/distroless/static-debian12
COPY --from=build /pricing-engine /pricing-engine
EXPOSE 8080
ENTRYPOINT ["/pricing-engine"]
